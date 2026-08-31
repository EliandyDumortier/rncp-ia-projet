#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MyDramaList audience sentiment scraper

Pipeline:
    PostgreSQL/Supabase
        -> first 10 dramas from kdrama.kdramas
        -> MyDramaList search
           (cloudscraper first, Playwright fallback)
        -> drama reviews
        -> viewer sentiment + ending reaction
        -> kdrama.drama_sentiments
        -> optional raw reviews in kdrama.drama_reviews

IMPORTANT:
This is a TEST RUNNER. It defaults to 10 dramas.

Run:
    python drama_sentiment_scraper.py

Later:
    python drama_sentiment_scraper.py --limit 1065 --workers 2

Dependencies:
    pip install pandas sqlalchemy psycopg2-binary python-dotenv
    pip install cloudscraper beautifulsoup4 aiohttp
    pip install playwright
    playwright install chromium
"""

import argparse
import asyncio
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urljoin, urlparse

import aiohttp
import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# ---------------------------------------------------------------------------
# ENVIRONMENT
# ---------------------------------------------------------------------------

THIS_FILE = Path(__file__).resolve()

for env_path in (
    Path.cwd() / ".env",
    THIS_FILE.parent / ".env",
    THIS_FILE.parents[1] / ".env",
    THIS_FILE.parents[2] / ".env",
):
    if env_path.exists():
        load_dotenv(env_path, override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("drama_sentiment_scraper")


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

MDL_BASE = "https://mydramalist.com"
DEFAULT_LIMIT = 10
DEFAULT_WORKERS = 2

REQUEST_TIMEOUT = 30
MAX_REVIEWS_PER_DRAMA = 40
MAX_REVIEW_PAGES = 4

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# DATABASE CONNECTION
# ---------------------------------------------------------------------------

def get_database_url() -> str:
    """
    Use the same environment variables expected by the previous scraper.
    """
    db_url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")

    if not db_url:
        raise RuntimeError(
            "Missing SUPABASE_DB_URL or DATABASE_URL in .env"
        )

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://"):]

    return db_url


class Database:
    def __init__(self):
        self.engine = create_engine(
            get_database_url(),
            pool_pre_ping=True,
            pool_recycle=1800,
        )

    def test(self):
        with self.engine.connect() as conn:
            value = conn.execute(text("SELECT 1")).scalar()
            if value != 1:
                raise RuntimeError("Database test failed.")

        logger.info("Database connection OK.")

    def get_dramas(self, limit: int | None = None) -> pd.DataFrame:
        """
        Read the actual dramas from the DB.

        We deliberately do not use the old JSON file.
        """
        query = text(
            """
            SELECT
                id,
                titre,
                english_name,
                titre_original,
                date_diffusion
            FROM kdrama.kdramas
            ORDER BY id
            """
        )

        with self.engine.connect() as conn:
            if limit is None:
                result = conn.execute(query)
            else:
                result = conn.execute(
                    text(
                        """
                        SELECT
                            id,
                            titre,
                            english_name,
                            titre_original,
                            date_diffusion
                        FROM kdrama.kdramas
                        ORDER BY id
                        LIMIT :limit
                        """
                    ),
                    {"limit": int(limit)},
                )
            rows = result.fetchall()
            columns = list(result.keys())

        df = pd.DataFrame(rows, columns=columns)

        logger.info(
            "Loaded %d dramas from kdrama.kdramas.",
            len(df),
        )

        for _, row in df.iterrows():
            logger.info(
                "  DB id=%s | titre=%r | english_name=%r",
                row["id"],
                row["titre"],
                row["english_name"],
            )

        return df

    def ensure_reviews_table(self) -> bool:
        """
        Keep raw reviews so we can improve the ML model later without
        scraping everything again.
        """
        query = text(
            """
            CREATE TABLE IF NOT EXISTS kdrama.drama_reviews (
                id BIGSERIAL PRIMARY KEY,
                drama_id BIGINT NOT NULL,
                source VARCHAR(50) NOT NULL,
                source_review_id VARCHAR(255),
                review_url TEXT,
                review_text TEXT NOT NULL,
                rating NUMERIC(4,2),
                review_sentiment NUMERIC(6,5),
                ending_signal VARCHAR(30),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (drama_id, source, source_review_id)
            )
            """
        )

        try:
            with self.engine.begin() as conn:
                conn.execute(query)

            logger.info(
                "kdrama.drama_reviews is available."
            )
            return True

        except Exception as exc:
            logger.warning(
                "Could not create kdrama.drama_reviews: %s",
                exc,
            )
            logger.warning(
                "Continuing without raw-review storage."
            )
            return False

    def save_reviews(
        self,
        drama_id: int,
        reviews: list[dict[str, Any]],
    ) -> int:
        if not reviews:
            return 0

        query = text(
            """
            INSERT INTO kdrama.drama_reviews
            (
                drama_id,
                source,
                source_review_id,
                review_url,
                review_text,
                rating,
                review_sentiment,
                ending_signal
            )
            VALUES
            (
                :drama_id,
                :source,
                :source_review_id,
                :review_url,
                :review_text,
                :rating,
                :review_sentiment,
                :ending_signal
            )
            ON CONFLICT (drama_id, source, source_review_id)
            DO UPDATE SET
                review_url = EXCLUDED.review_url,
                review_text = EXCLUDED.review_text,
                rating = EXCLUDED.rating,
                review_sentiment = EXCLUDED.review_sentiment,
                ending_signal = EXCLUDED.ending_signal
            """
        )

        saved = 0

        try:
            with self.engine.begin() as conn:
                for review in reviews:
                    conn.execute(
                        query,
                        {
                            "drama_id": drama_id,
                            "source": review["source"],
                            "source_review_id": review["source_review_id"],
                            "review_url": review.get("review_url"),
                            "review_text": review["review_text"],
                            "rating": review.get("rating"),
                            "review_sentiment": review.get(
                                "review_sentiment"
                            ),
                            "ending_signal": review.get(
                                "ending_signal"
                            ),
                        },
                    )
                    saved += 1

        except Exception as exc:
            logger.error(
                "Could not save raw reviews for drama %s: %s",
                drama_id,
                exc,
            )

        return saved

    def save_sentiment(
        self,
        drama_id: int,
        data: dict[str, Any],
    ) -> bool:
        """
        Write to the existing drama_sentiments table.

        Uses the columns from the original Claude scraper.
        """
        params = {
            "drama_id": int(drama_id),
            "ending_type": data.get("ending_type", "unknown"),
            "ending_confidence": float(
                data.get("ending_confidence", 0.0)
            ),
            "sentiment_score": float(
                data.get("sentiment_score", 0.5)
            ),
            "is_ongoing": bool(
                data.get("is_ongoing", False)
            ),
            "is_completed": bool(
                data.get("is_completed", True)
            ),
            # IMPORTANT: source_urls is a PostgreSQL ARRAY column.
            # Pass a Python list so psycopg2/SQLAlchemy adapts it
            # to a PostgreSQL array. Do NOT json.dumps() it.
            "source_urls": list(
                data.get("source_urls") or []
            ),
            "sentiment_summary": data.get(
                "sentiment_summary", ""
            ),
            "data_quality_score": float(
                data.get("data_quality_score", 0.0)
            ),
            "top_comments": json.dumps(
                data.get("top_comments") or [],
                ensure_ascii=False,
            ),
            "notable_triggers": data.get(
                "notable_triggers", []
            ),
            "viewer_consensus": data.get(
                "viewer_consensus", ""
            ),
        }

        try:
            logger.info(
                "DB WRITE | drama_id=%s | ending=%s | sentiment=%.4f | "
                "ending_confidence=%.4f | source_urls=%s",
                params["drama_id"],
                params["ending_type"],
                params["sentiment_score"],
                params["ending_confidence"],
                params["source_urls"],
            )

            logger.info(
                "DB WRITE DETAILS | quality=%.3f | consensus=%s | "
                "triggers=%s | top_comments=%d",
                params["data_quality_score"],
                params["viewer_consensus"],
                params["notable_triggers"],
                len(params["top_comments"]),
            )

            with self.engine.begin() as conn:
                exists = conn.execute(
                    text(
                        """
                        SELECT id
                        FROM kdrama.drama_sentiments
                        WHERE drama_id = :drama_id
                        """
                    ),
                    {"drama_id": int(drama_id)},
                ).fetchone()

                if exists:
                    conn.execute(
                        text(
                            """
                            UPDATE kdrama.drama_sentiments
                            SET
                                ending_type = :ending_type,
                                ending_confidence = :ending_confidence,
                                sentiment_score = :sentiment_score,
                                is_ongoing = :is_ongoing,
                                is_completed = :is_completed,
                                source_urls = CAST(:source_urls AS text[]),
                                sentiment_summary = :sentiment_summary,
                                data_quality_score = :data_quality_score,
                                top_comments = :top_comments,
                                notable_triggers = CAST(:notable_triggers AS text[]),
                                viewer_consensus = :viewer_consensus,
                                last_updated = CURRENT_TIMESTAMP
                            WHERE drama_id = :drama_id
                            """
                        ),
                        params,
                    )
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO kdrama.drama_sentiments
                            (
                                drama_id,
                                ending_type,
                                ending_confidence,
                                sentiment_score,
                                is_ongoing,
                                is_completed,
                                source_urls,
                                sentiment_summary,
                                data_quality_score,
                                top_comments,
                                notable_triggers,
                                viewer_consensus
                            )
                            VALUES
                            (
                                :drama_id,
                                :ending_type,
                                :ending_confidence,
                                :sentiment_score,
                                :is_ongoing,
                                :is_completed,
                                CAST(:source_urls AS text[]),
                                :sentiment_summary,
                                :data_quality_score,
                                :top_comments,
                                CAST(:notable_triggers AS text[]),
                                :viewer_consensus
                            )
                            """
                        ),
                        params,
                    )

            return True

        except Exception as exc:
            logger.error(
                "Could not save sentiment for drama %s: %s",
                drama_id,
                exc,
            )
            return False


# ---------------------------------------------------------------------------
# SENTIMENT
# ---------------------------------------------------------------------------

POSITIVE_WORDS = {
    "love", "loved", "amazing", "beautiful", "perfect",
    "wonderful", "excellent", "great", "good", "satisfying",
    "satisfied", "heartwarming", "masterpiece", "brilliant",
    "emotional", "enjoyed", "enjoyable", "cute", "funny",
    "happy", "hopeful", "healing", "meaningful", "favorite",
    "favourite", "recommend", "recommended", "fantastic",
    "awesome", "superb", "incredible", "entertaining",
}

NEGATIVE_WORDS = {
    "hate", "hated", "terrible", "awful", "bad", "worst",
    "boring", "disappointing", "disappointed", "ruined",
    "mess", "waste", "sad", "depressing", "heartbreaking",
    "painful", "tragic", "frustrating", "frustrated", "angry",
    "unhappy", "regret", "cringe", "cringey", "weak",
    "predictable", "slow", "dragged", "dislike", "disliked",
}

HAPPY_ENDING_PHRASES = [
    "happy ending", "satisfying ending", "satisfying conclusion",
    "finally together", "end up together", "ended up together",
    "they get married", "they got married", "gets married",
    "got married", "reunited", "together in the end",
    "together at the end", "love wins", "well deserved ending",
    "great ending", "good ending", "perfect ending",
]

SAD_ENDING_PHRASES = [
    "sad ending", "tragic ending", "heartbreaking ending",
    "heartbroken", "dies in the end", "died in the end",
    "death in the finale", "tragic finale", "they separate",
    "they separated", "ends in tragedy", "sad finale",
    "depressing ending", "devastating ending",
]

MIXED_ENDING_PHRASES = [
    "bittersweet", "mixed feelings", "mixed emotions",
    "happy and sad", "sad but", "sad yet",
    "beautiful but sad", "happy but sad", "beautiful ending but",
]

ASPECT_TRIGGERS = {
    "story": [
        "story", "plot", "writing", "script", "storyline",
        "narrative", "plot twist",
    ],
    "characters": [
        "character", "characters", "protagonist", "villain",
        "character development",
    ],
    "romance": [
        "romance", "romantic", "chemistry", "couple",
        "love story", "relationship",
    ],
    "acting": [
        "acting", "actor", "actress", "performance", "cast",
        "chemistry",
    ],
    "pacing": [
        "pacing", "paced", "slow", "dragged", "dragging",
        "fast paced", "fast-paced",
    ],
    "comedy": [
        "funny", "comedy", "hilarious", "humor", "humour",
        "laugh", "laughing",
    ],
    "ending": [
        "ending", "finale", "final episode", "last episode",
        "conclusion",
    ],
    "ost": [
        "ost", "soundtrack", "music", "song",
    ],
    "production": [
        "cinematography", "visuals", "production", "costume",
        "costumes", "beautifully shot",
    ],
}

def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def tokenize(text_value: str) -> list[str]:
    return re.findall(
        r"[a-z']+",
        clean_text(text_value).lower(),
    )


def keyword_sentiment(text_value: str) -> float:
    """
    Transparent fallback sentiment.

    IMPORTANT:
    This is not presented as an ML sentiment model. It is only used when
    the review's numeric rating cannot be extracted.
    """
    tokens = tokenize(text_value)

    positive = sum(
        1 for token in tokens
        if token in POSITIVE_WORDS
    )
    negative = sum(
        1 for token in tokens
        if token in NEGATIVE_WORDS
    )

    total = positive + negative

    if total == 0:
        return 0.5

    # Convert a positive-vs-negative balance to 0..1.
    return round(
        0.5 + 0.5 * ((positive - negative) / total),
        4,
    )


def rating_to_sentiment(rating: Optional[float]) -> Optional[float]:
    """
    Convert MDL's 0..10 review rating to 0..1.

    The official MDL review object includes an overall rating when using
    the API; our HTML scraper uses this when it can extract it.
    """
    if rating is None:
        return None

    try:
        rating = float(rating)
    except (TypeError, ValueError):
        return None

    if not 0 <= rating <= 10:
        return None

    return round(rating / 10.0, 4)


def review_sentiment(text_value: str, rating: Optional[float] = None) -> float:
    """
    Prefer the reviewer's numeric rating when available.
    Fall back to transparent text sentiment otherwise.
    """
    rating_score = rating_to_sentiment(rating)

    if rating_score is not None:
        return rating_score

    return keyword_sentiment(text_value)


def ending_signal(text_value: str) -> Optional[str]:
    text_value = clean_text(text_value).lower()

    mixed = sum(
        phrase in text_value
        for phrase in MIXED_ENDING_PHRASES
    )
    happy = sum(
        phrase in text_value
        for phrase in HAPPY_ENDING_PHRASES
    )
    sad = sum(
        phrase in text_value
        for phrase in SAD_ENDING_PHRASES
    )

    if mixed:
        return "bittersweet"

    if happy and sad:
        return "bittersweet"

    if happy > sad and happy:
        return "happy"

    if sad > happy and sad:
        return "sad"

    return None


def detect_triggers(text_value: str) -> list[str]:
    """
    Extract interpretable audience themes from the actual review text.
    """
    lower = clean_text(text_value).lower()
    found = []

    for aspect, phrases in ASPECT_TRIGGERS.items():
        if any(phrase in lower for phrase in phrases):
            found.append(aspect)

    return found


def analyze_reviews(
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Produce all audience-facing fields needed by drama_sentiments.

    The output is deliberately deterministic and traceable to the raw
    reviews stored in kdrama.drama_reviews.
    """
    if not reviews:
        return {
            "sentiment_score": 0.5,
            "ending_type": "unknown",
            "ending_confidence": 0.0,
            "sentiment_summary": "",
            "data_quality_score": 0.0,
            "top_comments": [],
            "notable_triggers": [],
            "viewer_consensus": "",
        }

    # Scores: ratings first, text fallback second.
    scores = [
        float(review["review_sentiment"])
        for review in reviews
        if review.get("review_sentiment") is not None
    ]

    sentiment = (
        sum(scores) / len(scores)
        if scores
        else 0.5
    )

    # Ending vote.
    ending_counts = {
        "happy": 0,
        "sad": 0,
        "bittersweet": 0,
    }

    for review in reviews:
        signal = review.get("ending_signal")
        if signal in ending_counts:
            ending_counts[signal] += 1

    ending_votes = sum(ending_counts.values())

    if ending_votes == 0:
        ending = "unknown"
        ending_confidence = 0.0
    else:
        ordered = sorted(
            ending_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        winner, winner_count = ordered[0]
        runner_up_count = ordered[1][1]

        # A one-vote margin is not strong enough to call a definitive
        # happy/sad ending. Preserve ambiguity as bittersweet.
        if (
            winner_count == runner_up_count
            or winner_count - runner_up_count <= 1
        ):
            ending = "bittersweet"
            ending_confidence = 0.5
        else:
            ending = winner
            ending_confidence = round(
                winner_count / ending_votes,
                4,
            )

    # Consensus uses the overall score, not ending type.
    if sentiment >= 0.80:
        consensus = "strongly positive"
    elif sentiment >= 0.65:
        consensus = "positive"
    elif sentiment >= 0.55:
        consensus = "mixed-positive"
    elif sentiment > 0.45:
        consensus = "mixed"
    elif sentiment > 0.35:
        consensus = "mixed-negative"
    elif sentiment > 0.20:
        consensus = "negative"
    else:
        consensus = "strongly negative"

    # Collect aspect triggers across reviews.
    trigger_counts = {}
    for review in reviews:
        for trigger in review.get("triggers", []):
            trigger_counts[trigger] = (
                trigger_counts.get(trigger, 0) + 1
            )

    notable_triggers = [
        aspect
        for aspect, count in sorted(
            trigger_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if count >= 2
    ][:8]

    # Representative comments: prioritize high-confidence / high-rated
    # reviews and keep excerpts short enough for a DB text field.
    def comment_score(review):
        score = float(
            review.get("review_sentiment", 0.5)
        )
        rating = review.get("rating")
        rating_bonus = (
            float(rating) / 10.0
            if rating is not None
            else score
        )
        return 0.6 * score + 0.4 * rating_bonus

    ranked = sorted(
        reviews,
        key=comment_score,
        reverse=True,
    )

    top_comments = []
    for review in ranked[:5]:
        excerpt = clean_text(
            review["review_text"]
        )

        if len(excerpt) > 500:
            excerpt = excerpt[:497].rsplit(" ", 1)[0] + "..."

        top_comments.append(excerpt)

    # Quality score reflects evidence, not positivity.
    rating_coverage = (
        sum(
            review.get("rating") is not None
            for review in reviews
        ) / len(reviews)
    )

    ending_coverage = (
        ending_votes / len(reviews)
    )

    review_volume_score = min(
        len(reviews) / 40.0,
        1.0,
    )

    quality = (
        0.45 * review_volume_score
        + 0.30 * rating_coverage
        + 0.25 * ending_coverage
    )

    quality = round(
        min(max(quality, 0.0), 1.0),
        4,
    )

    # Human-readable summary derived from the aggregate fields.
    if ending == "unknown":
        ending_phrase = "The scraped reviews did not contain enough explicit ending reactions."
    elif ending == "bittersweet":
        ending_phrase = "Reviewers showed mixed or bittersweet reactions to the ending."
    elif ending == "happy":
        ending_phrase = "Reviewers who discussed the ending leaned happy or satisfied."
    else:
        ending_phrase = "Reviewers who discussed the ending leaned sad or tragic."

    trigger_phrase = (
        ", ".join(notable_triggers[:4])
        if notable_triggers
        else "no dominant theme detected"
    )

    summary = (
        f"Audience reaction was {consensus} "
        f"(score {sentiment:.2f}). "
        f"{ending_phrase} "
        f"Frequent themes: {trigger_phrase}."
    )

    return {
        "sentiment_score": round(sentiment, 4),
        "ending_type": ending,
        "ending_confidence": round(
            ending_confidence,
            4,
        ),
        "sentiment_summary": summary,
        "data_quality_score": quality,
        "top_comments": top_comments,
        "notable_triggers": notable_triggers,
        "viewer_consensus": consensus,
    }


# ---------------------------------------------------------------------------
# MYDRAMALIST ACCESS
# ---------------------------------------------------------------------------

class MDLClient:
    """
    Reuses the successful strategy from the reference scraper:

        cloudscraper -> Playwright fallback

    cloudscraper is tried first because it is much faster than launching
    Chromium for every drama.
    """

    def __init__(self):
        self._local = threading.local()

    def _get_scraper(self):
        if not hasattr(self._local, "scraper"):
            self._local.scraper = cloudscraper.create_scraper(
                browser={
                    "browser": "chrome",
                    "platform": "windows",
                    "mobile": False,
                }
            )
        return self._local.scraper

    def get_with_cloudscraper(
        self,
        url: str,
    ) -> Optional[str]:
        scraper = self._get_scraper()

        try:
            response = scraper.get(
                url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                logger.warning(
                    "MDL cloudscraper HTTP %s: %s",
                    response.status_code,
                    url,
                )
                return None

            html = response.text

            if self.looks_blocked(html):
                logger.warning(
                    "MDL returned a block/Cloudflare page: %s",
                    url,
                )
                return None

            return html

        except Exception as exc:
            logger.warning(
                "cloudscraper failed for %s: %s",
                url,
                exc,
            )
            return None

    @staticmethod
    def looks_blocked(html: str) -> bool:
        lower = html.lower()

        markers = [
            "cf-chl-",
            "just a moment...",
            "verify you are human",
            "checking your browser",
            "access denied",
            "attention required",
        ]

        return any(marker in lower for marker in markers)

    def get_with_playwright_sync(
        self,
        url: str,
    ) -> Optional[str]:
        """
        Playwright fallback based on the working reference scraper.

        This is synchronous on purpose and is executed in a worker thread
        so several dramas can still be processed without blocking asyncio.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error(
                "Playwright is not installed. "
                "Install with: pip install playwright && "
                "playwright install chromium"
            )
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True
                )

                page = browser.new_page(
                    user_agent=HEADERS["User-Agent"],
                    locale="en-US",
                )

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=REQUEST_TIMEOUT * 1000,
                )

                # Give Cloudflare/JS a moment if present.
                page.wait_for_timeout(2500)

                html = page.content()

                browser.close()

            if self.looks_blocked(html):
                logger.warning(
                    "Playwright still received a block page: %s",
                    url,
                )
                return None

            return html

        except Exception as exc:
            logger.error(
                "Playwright failed for %s: %s",
                url,
                exc,
            )
            return None

    async def get_html(self, url: str) -> Optional[str]:
        """
        cloudscraper first, Playwright second.
        """
        html = await asyncio.to_thread(
            self.get_with_cloudscraper,
            url,
        )

        if html:
            return html

        logger.info(
            "Trying Playwright fallback for %s",
            url,
        )

        return await asyncio.to_thread(
            self.get_with_playwright_sync,
            url,
        )

    @staticmethod
    def normalize_title(title: str) -> str:
        title = clean_text(title).lower()
        title = re.sub(r"[^\w\s]", " ", title)
        title = re.sub(r"\s+", " ", title)
        return title.strip()

    def choose_result(
        self,
        soup: BeautifulSoup,
        requested_title: str,
    ) -> Optional[str]:
        requested = self.normalize_title(
            requested_title
        )

        candidates: list[tuple[float, str]] = []

        for link in soup.find_all("a", href=True):
            href = str(link["href"])

            # Typical MDL title URLs have a numeric slug:
            # /12345-title
            if not re.match(r"^/\d+[-/]", href):
                continue

            text_value = clean_text(
                link.get_text(" ", strip=True)
            )

            title_attr = clean_text(
                str(link.get("title", ""))
            )

            aria = clean_text(
                str(link.get("aria-label", ""))
            )

            candidate_texts = [
                text_value,
                title_attr,
                aria,
            ]

            score = 0.0

            for candidate in candidate_texts:
                normalized = self.normalize_title(
                    candidate
                )

                if not normalized:
                    continue

                if normalized == requested:
                    score = max(score, 20)

                elif (
                    requested in normalized
                    or normalized in requested
                ):
                    score = max(score, 10)

                # Word overlap helps with subtitles / punctuation.
                requested_words = set(
                    requested.split()
                )
                candidate_words = set(
                    normalized.split()
                )

                if requested_words:
                    overlap = len(
                        requested_words
                        & candidate_words
                    ) / len(requested_words)

                    score = max(
                        score,
                        overlap * 8,
                    )

            if score > 0:
                candidates.append(
                    (
                        score,
                        urljoin(
                            MDL_BASE,
                            href,
                        ),
                    )
                )

        if not candidates:
            return None

        candidates.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        return candidates[0][1]

    async def search(
        self,
        title: str,
    ) -> Optional[str]:
        if not title:
            return None

        url = (
            f"{MDL_BASE}/search?q="
            f"{quote(title)}"
        )

        html = await self.get_html(url)

        if not html:
            return None

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        result = self.choose_result(
            soup,
            title,
        )

        if result:
            logger.info(
                "MDL match: %r -> %s",
                title,
                result,
            )
        else:
            logger.warning(
                "MDL page loaded but no matching drama "
                "was found for %r",
                title,
            )

        return result

    @staticmethod
    def extract_rating(
        element: Any,
    ) -> Optional[float]:
        for attr in (
            "data-rating",
            "data-score",
            "data-value",
        ):
            value = element.get(attr)

            if value:
                try:
                    rating = float(
                        str(value).replace(",", ".")
                    )

                    if 0 <= rating <= 10:
                        return rating
                except ValueError:
                    pass

        text_value = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        patterns = [
            r"\b(10(?:\.0)?|[0-9](?:\.[0-9])?)\s*/\s*10\b",
            r"\b(?:rating|score)\s*[:\-]?\s*"
            r"(10(?:\.0)?|[0-9](?:\.[0-9])?)\b",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text_value,
                re.I,
            )

            if match:
                try:
                    rating = float(
                        match.group(1)
                    )

                    if 0 <= rating <= 10:
                        return rating
                except ValueError:
                    pass

        return None

    @staticmethod
    def review_containers(
        soup: BeautifulSoup,
    ) -> list[Any]:
        """
        MDL markup can change, so use several selectors.
        """
        selectors = [
            "div.review",
            "article.review",
            "div.review-item",
            "div.review-list-item",
            "[class*='review-item']",
            "[class*='review-list-item']",
        ]

        found = []

        for selector in selectors:
            try:
                for element in soup.select(selector):
                    if element in found:
                        continue

                    txt = clean_text(
                        element.get_text(
                            " ",
                            strip=True,
                        )
                    )

                    if len(txt) >= 80:
                        found.append(element)

            except Exception:
                continue

        # Remove nested duplicates.
        output = []

        for element in found:
            nested = False

            for other in found:
                if (
                    element is not other
                    and element in other.descendants
                ):
                    nested = True
                    break

            if not nested:
                output.append(element)

        return output

    def parse_reviews(
        self,
        html: str,
        page_url: str,
    ) -> list[dict[str, Any]]:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        containers = self.review_containers(
            soup
        )

        reviews = []

        for index, element in enumerate(containers):
            review_text = clean_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if len(review_text) < 80:
                continue

            lower = review_text.lower()

            if (
                "write a review" in lower
                and len(review_text) < 250
            ):
                continue

            # Try to find a review-specific link.
            review_url = page_url

            for link in element.find_all(
                "a",
                href=True,
            ):
                href = str(link["href"])

                if "review" in href.lower():
                    review_url = urljoin(
                        MDL_BASE,
                        href,
                    )
                    break

            source_id = None

            for attr in (
                "data-id",
                "data-review-id",
                "id",
            ):
                if element.get(attr):
                    source_id = str(
                        element.get(attr)
                    )
                    break

            if not source_id:
                source_id = (
                    f"{page_url}#review-{index}"
                )

            rating = self.extract_rating(
                element
            )

            # Try to capture a review headline separately.
            headline = ""
            for selector in (
                ".review-title",
                ".review-headline",
                "h3",
                "h4",
                "[class*='headline']",
                "[class*='title']",
            ):
                candidate = element.select_one(
                    selector
                )
                if candidate:
                    headline = clean_text(
                        candidate.get_text(
                            " ",
                            strip=True,
                        )
                    )
                    if headline:
                        break

            analysis_text = clean_text(
                f"{headline}. {review_text}"
            )

            reviews.append(
                {
                    "source": "mydramalist",
                    "source_review_id": source_id,
                    "review_url": review_url,
                    "review_text": review_text,
                    "headline": headline,
                    "rating": rating,
                    "review_sentiment": review_sentiment(
                        analysis_text,
                        rating,
                    ),
                    "ending_signal": ending_signal(
                        analysis_text
                    ),
                    "triggers": detect_triggers(
                        analysis_text
                    ),
                }
            )

        return reviews

    async def reviews(
        self,
        drama_url: str,
        max_reviews: int = MAX_REVIEWS_PER_DRAMA,
        max_pages: int = MAX_REVIEW_PAGES,
    ) -> dict[str, Any]:
        parsed = urlparse(drama_url)
        path = parsed.path.rstrip("/")

        if path.endswith("/reviews"):
            base = drama_url.rstrip("/")
        else:
            base = drama_url.rstrip("/") + "/reviews"

        all_reviews = []
        seen_ids = set()
        is_ongoing = False

        for page_number in range(1, max_pages + 1):
            url = (
                base
                if page_number == 1
                else f"{base}?page={page_number}"
            )

            logger.info(
                "Fetching MDL reviews page %d: %s",
                page_number,
                url,
            )

            html = await self.get_html(url)

            if not html:
                logger.warning(
                    "Could not load review page %d.",
                    page_number,
                )
                break

            # Do not infer airing status from the entire HTML page:
            # review text itself can contain words such as "ongoing".
            # Only inspect likely status elements.
            status_texts = []
            soup_status = BeautifulSoup(
                html,
                "html.parser",
            )

            for selector in (
                ".show-status",
                ".info-item",
                ".box-header",
                "[class*='status']",
            ):
                for element in soup_status.select(selector):
                    value = clean_text(
                        element.get_text(" ", strip=True)
                    )
                    if value:
                        status_texts.append(value.lower())

            status_blob = " ".join(status_texts)

            if (
                "ongoing" in status_blob
                or "currently airing" in status_blob
                or "airing" in status_blob
            ):
                is_ongoing = True

            page_reviews = self.parse_reviews(
                html,
                url,
            )

            if not page_reviews:
                logger.info(
                    "No review containers found on page %d.",
                    page_number,
                )
                break

            new_reviews = 0

            for review in page_reviews:
                rid = review[
                    "source_review_id"
                ]

                if rid in seen_ids:
                    continue

                seen_ids.add(rid)
                all_reviews.append(review)
                new_reviews += 1

                if len(all_reviews) >= max_reviews:
                    break

            logger.info(
                "Reviews page %d: %d new, %d total",
                page_number,
                new_reviews,
                len(all_reviews),
            )

            if (
                new_reviews == 0
                or len(all_reviews) >= max_reviews
            ):
                break

            await asyncio.sleep(1.0)

        return {
            "reviews": all_reviews[:max_reviews],
            "url": base,
            "is_ongoing": is_ongoing,
        }


# ---------------------------------------------------------------------------
# ONE DRAMA
# ---------------------------------------------------------------------------

async def process_drama(
    db: Database,
    mdl: MDLClient,
    row: pd.Series,
    reviews_table_available: bool,
) -> bool:
    drama_id = int(row["id"])
    db_title = clean_text(
        str(row.get("titre") or "")
    )

    english_name = None

    if pd.notna(row.get("english_name")):
        english_name = clean_text(
            str(row["english_name"])
        )

    # Prefer English title, then DB title.
    search_titles = []

    if english_name:
        search_titles.append(
            english_name
        )

    if (
        db_title
        and db_title not in search_titles
    ):
        search_titles.append(
            db_title
        )

    logger.info("=" * 70)
    logger.info(
        "DRAMA DB id=%s | titles=%s",
        drama_id,
        search_titles,
    )

    mdl_url = None

    for title in search_titles:
        logger.info(
            "Searching MDL for %r",
            title,
        )

        mdl_url = await mdl.search(title)

        if mdl_url:
            break

    if not mdl_url:
        logger.warning(
            "FAILED TO FIND MDL DRAMA | DB id=%s",
            drama_id,
        )
        return False

    data = await mdl.reviews(
        mdl_url
    )

    reviews = data["reviews"]

    if not reviews:
        logger.warning(
            "MDL drama found, but NO REVIEWS | "
            "DB id=%s | %s",
            drama_id,
            mdl_url,
        )

        # No fake audience result.
        db.save_sentiment(
            drama_id,
            {
                "ending_type": "unknown",
                "ending_confidence": 0.0,
                "sentiment_score": 0.5,
                "sentiment_summary": (
                    "No usable viewer reviews were scraped."
                ),
                "data_quality_score": 0.0,
                "top_comments": [],
                "notable_triggers": [],
                "viewer_consensus": "insufficient data",
                "is_ongoing": data[
                    "is_ongoing"
                ],
                "is_completed": not data[
                    "is_ongoing"
                ],
                "source_urls": [
                    mdl_url,
                    data["url"],
                ],
            },
        )

        return False

    if reviews_table_available:
        saved = db.save_reviews(
            drama_id,
            reviews,
        )

        logger.info(
            "Saved %d raw reviews for DB id=%s",
            saved,
            drama_id,
        )

    aggregate = analyze_reviews(
        reviews
    )

    result = {
        "ending_type": aggregate[
            "ending_type"
        ],
        "ending_confidence": aggregate[
            "ending_confidence"
        ],
        "sentiment_score": aggregate[
            "sentiment_score"
        ],
        "sentiment_summary": aggregate[
            "sentiment_summary"
        ],
        "data_quality_score": aggregate[
            "data_quality_score"
        ],
        "top_comments": aggregate[
            "top_comments"
        ],
        "notable_triggers": aggregate[
            "notable_triggers"
        ],
        "viewer_consensus": aggregate[
            "viewer_consensus"
        ],
        "is_ongoing": data[
            "is_ongoing"
        ],
        "is_completed": not data[
            "is_ongoing"
        ],
        "source_urls": [
            mdl_url,
            data["url"],
        ],
    }

    logger.info(
        "RESULT | DB id=%s | reviews=%d | "
        "sentiment=%.3f | ending=%s | confidence=%.3f",
        drama_id,
        len(reviews),
        result["sentiment_score"],
        result["ending_type"],
        result["ending_confidence"],
    )

    # Print a few real viewer texts so we can verify
    # that we are collecting reviews rather than page/navigation text.
    for index, review in enumerate(
        reviews[:3],
        start=1,
    ):
        preview = review[
            "review_text"
        ][:300]

        logger.info(
            "  REVIEW %d | rating=%s | sentiment=%.3f | "
            "ending=%s | %s",
            index,
            review.get("rating"),
            review["review_sentiment"],
            review.get("ending_signal"),
            preview,
        )

    if db.save_sentiment(
        drama_id,
        result,
    ):
        logger.info(
            "SAVED sentiment for DB id=%s",
            drama_id,
        )
        return True

    return False


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

async def run(
    limit: int,
    workers: int,
):
    db = Database()

    # FIRST: prove the DB works.
    db.test()

    reviews_table_available = (
        db.ensure_reviews_table()
    )

    dramas = db.get_dramas(
        limit=limit
    )

    if dramas.empty:
        logger.warning(
            "No dramas found."
        )
        return

    mdl = MDLClient()

    semaphore = asyncio.Semaphore(
        workers
    )

    async def limited(row):
        async with semaphore:
            try:
                return await process_drama(
                    db,
                    mdl,
                    row,
                    reviews_table_available,
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected error for DB id=%s: %s",
                    row["id"],
                    exc,
                )
                return False

    tasks = [
        asyncio.create_task(
            limited(row)
        )
        for _, row in dramas.iterrows()
    ]

    results = await asyncio.gather(
        *tasks
    )

    successful = sum(results)
    failed = len(results) - successful

    logger.info("=" * 70)
    logger.info(
        "FINISHED | successful=%d | failed=%d | total=%d",
        successful,
        failed,
        len(results),
    )


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional test limit. Omit to process every drama.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.limit is not None and args.limit < 1:
        raise SystemExit(
            "--limit must be at least 1"
        )

    if args.workers < 1:
        raise SystemExit(
            "--workers must be at least 1"
        )

    asyncio.run(
        run(
            args.limit,
            args.workers,
        )
    )


if __name__ == "__main__":
    main()
