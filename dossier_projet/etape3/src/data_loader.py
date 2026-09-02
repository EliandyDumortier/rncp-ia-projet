#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_loader.py — Chargement du catalogue et des interactions K-Dramas.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

_THIS_FILE = Path(__file__).resolve()
if "dossier_projet" in _THIS_FILE.parts:
    _PROJECT_ROOT = _THIS_FILE.parents[3]
else:
    _PROJECT_ROOT = _THIS_FILE.parents[1]

for _env_path in (
    Path.cwd() / ".env",
    _PROJECT_ROOT / ".env",
    _PROJECT_ROOT / "dossier_projet" / "etape3" / ".env",
    _PROJECT_ROOT / "dossier_projet" / "etape1" / ".env",
):
    load_dotenv(_env_path, override=False)

RANDOM_STATE = 42
MIN_REAL_INTERACTIONS = 25


def _is_env_true(var_name: str, default: bool = False) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_snapshot_path() -> Path:
    custom_path = os.getenv("LOCAL_DATA_SNAPSHOT_PATH")
    if custom_path:
        return Path(custom_path).expanduser().resolve()

    return (
        _PROJECT_ROOT
        / "dossier_projet"
        / "etape1"
        / "data"
        / "clean"
        / "kdramas_clean.json"
    )


def _normalize_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return []
        if text_value.startswith("[") and text_value.endswith("]"):
            try:
                decoded = json.loads(text_value)
                raw_items = decoded if isinstance(decoded, list) else [decoded]
            except json.JSONDecodeError:
                raw_items = text_value.split(",")
        else:
            raw_items = text_value.split(",")
    else:
        raw_items = [value]

    normalized: list[str] = []
    for item in raw_items:
        clean = str(item).strip().strip("[]\"'")
        if clean and clean.lower() != "nan" and clean not in normalized:
            normalized.append(clean)
    return normalized


def _load_embedded_catalog() -> pd.DataFrame:
    seed_catalog = [
        {
            "drama_id": 1,
            "title": "Crash Landing on You",
            "synopsis": "A South Korean heiress crash-lands in North Korea.",
            "genres": "Romance, Drama",
            "note_moyenne": 8.8,
            "date_diffusion": "2019-01-01",
            "nb_votes": 1000,
            "nb_episodes": 16,
            "reseaux_diffusion": "tvN",
            "acteurs": "Hyun Bin, Son Ye-jin",
            "poster": "",
            "ending_type": "happy",
            "sentiment_score": 0.82,
            "top_comments": "",
            "viewer_consensus": "Warm romance with a satisfying ending.",
            "sentiment_summary": "Emotional and uplifting.",
            "principal_actors": "Hyun Bin, Son Ye-jin",
        },
        {
            "drama_id": 2,
            "title": "Kingdom",
            "synopsis": "A crown prince investigates a mysterious plague.",
            "genres": "Thriller, Historical",
            "note_moyenne": 8.5,
            "date_diffusion": "2019-01-01",
            "nb_votes": 1000,
            "nb_episodes": 12,
            "reseaux_diffusion": "Netflix",
            "acteurs": "Ju Ji-hoon, Bae Doona",
            "poster": "",
            "ending_type": "bittersweet",
            "sentiment_score": 0.12,
            "top_comments": "",
            "viewer_consensus": "Dark, tense and suspenseful.",
            "sentiment_summary": "A gripping thriller.",
            "principal_actors": "Ju Ji-hoon, Bae Doona",
        },
        {
            "drama_id": 3,
            "title": "Goblin",
            "synopsis": "An immortal seeks his destined bride to end his curse.",
            "genres": "Fantasy, Romance",
            "note_moyenne": 8.7,
            "date_diffusion": "2016-01-01",
            "nb_votes": 1000,
            "nb_episodes": 16,
            "reseaux_diffusion": "tvN",
            "acteurs": "Gong Yoo, Kim Go-eun",
            "poster": "",
            "ending_type": "bittersweet",
            "sentiment_score": 0.42,
            "top_comments": "",
            "viewer_consensus": "Epic fantasy romance with emotional highs.",
            "sentiment_summary": "Romantic and emotional.",
            "principal_actors": "Gong Yoo, Kim Go-eun",
        },
        {
            "drama_id": 4,
            "title": "Signal",
            "synopsis": "Detectives communicate across time using an old radio.",
            "genres": "Crime, Thriller",
            "note_moyenne": 8.6,
            "date_diffusion": "2016-01-01",
            "nb_votes": 1000,
            "nb_episodes": 16,
            "reseaux_diffusion": "tvN",
            "acteurs": "Lee Je-hoon, Kim Hye-soo",
            "poster": "",
            "ending_type": "unknown",
            "sentiment_score": 0.05,
            "top_comments": "",
            "viewer_consensus": "Smart and tense investigative drama.",
            "sentiment_summary": "Suspenseful and cerebral.",
            "principal_actors": "Lee Je-hoon, Kim Hye-soo",
        },
        {
            "drama_id": 5,
            "title": "Reply 1988",
            "synopsis": "Families and friends grow together in a Seoul neighborhood.",
            "genres": "Family, Comedy",
            "note_moyenne": 9.0,
            "date_diffusion": "2015-01-01",
            "nb_votes": 1000,
            "nb_episodes": 20,
            "reseaux_diffusion": "tvN",
            "acteurs": "Lee Hye-ri, Park Bo-gum",
            "poster": "",
            "ending_type": "happy",
            "sentiment_score": 0.88,
            "top_comments": "",
            "viewer_consensus": "Comforting and nostalgic.",
            "sentiment_summary": "Heartwarming slice of life.",
            "principal_actors": "Lee Hye-ri, Park Bo-gum",
        },
        {
            "drama_id": 6,
            "title": "Itaewon Class",
            "synopsis": "An ex-con opens a pub to challenge a powerful food company.",
            "genres": "Drama, Business",
            "note_moyenne": 8.2,
            "date_diffusion": "2020-01-01",
            "nb_votes": 1000,
            "nb_episodes": 16,
            "reseaux_diffusion": "JTBC",
            "acteurs": "Park Seo-joon, Kim Da-mi",
            "poster": "",
            "ending_type": "happy",
            "sentiment_score": 0.65,
            "top_comments": "",
            "viewer_consensus": "Motivating underdog story.",
            "sentiment_summary": "Driven and hopeful.",
            "principal_actors": "Park Seo-joon, Kim Da-mi",
        },
        {
            "drama_id": 7,
            "title": "Vincenzo",
            "synopsis": "A Korean-Italian consigliere fights corruption in Seoul.",
            "genres": "Action, Dark Comedy",
            "note_moyenne": 8.4,
            "date_diffusion": "2021-01-01",
            "nb_votes": 1000,
            "nb_episodes": 20,
            "reseaux_diffusion": "tvN",
            "acteurs": "Song Joong-ki, Jeon Yeo-been",
            "poster": "",
            "ending_type": "happy",
            "sentiment_score": 0.54,
            "top_comments": "",
            "viewer_consensus": "Stylish revenge with dark humor.",
            "sentiment_summary": "Sharp and entertaining.",
            "principal_actors": "Song Joong-ki, Jeon Yeo-been",
        },
        {
            "drama_id": 8,
            "title": "My Mister",
            "synopsis": "Two struggling souls find comfort in each other.",
            "genres": "Drama, Slice of Life",
            "note_moyenne": 9.1,
            "date_diffusion": "2018-01-01",
            "nb_votes": 1000,
            "nb_episodes": 16,
            "reseaux_diffusion": "tvN",
            "acteurs": "Lee Sun-kyun, IU",
            "poster": "",
            "ending_type": "bittersweet",
            "sentiment_score": 0.36,
            "top_comments": "",
            "viewer_consensus": "Healing but emotionally heavy.",
            "sentiment_summary": "Deep and reflective.",
            "principal_actors": "Lee Sun-kyun, IU",
        },
        {
            "drama_id": 9,
            "title": "Hospital Playlist",
            "synopsis": "Five doctor friends navigate life and work in a hospital.",
            "genres": "Medical, Friendship",
            "note_moyenne": 8.9,
            "date_diffusion": "2020-01-01",
            "nb_votes": 1000,
            "nb_episodes": 12,
            "reseaux_diffusion": "tvN",
            "acteurs": "Jo Jung-suk, Yoo Yeon-seok",
            "poster": "",
            "ending_type": "happy",
            "sentiment_score": 0.8,
            "top_comments": "",
            "viewer_consensus": "Comforting friendships and gentle humor.",
            "sentiment_summary": "Warm ensemble drama.",
            "principal_actors": "Jo Jung-suk, Yoo Yeon-seok",
        },
        {
            "drama_id": 10,
            "title": "Flower of Evil",
            "synopsis": "A detective suspects her husband hides a dark past.",
            "genres": "Mystery, Romance",
            "note_moyenne": 8.6,
            "date_diffusion": "2020-01-01",
            "nb_votes": 1000,
            "nb_episodes": 16,
            "reseaux_diffusion": "tvN",
            "acteurs": "Lee Joon-gi, Moon Chae-won",
            "poster": "",
            "ending_type": "happy",
            "sentiment_score": 0.47,
            "top_comments": "",
            "viewer_consensus": "Dark suspense balanced by romance.",
            "sentiment_summary": "Intense and emotional.",
            "principal_actors": "Lee Joon-gi, Moon Chae-won",
        },
    ]

    dramas_df = pd.DataFrame(seed_catalog)
    logger.warning(
        "Using embedded K-Drama catalog fallback (%d rows).",
        len(dramas_df),
    )
    return dramas_df


def _load_dramas_from_snapshot(snapshot_path: Path | None = None) -> pd.DataFrame:
    path = snapshot_path or _get_snapshot_path()
    if not path.exists():
        logger.warning("Local snapshot not found: %s", path)
        return _load_embedded_catalog()

    raw_df = pd.read_json(path) if path.suffix.lower() == ".json" else pd.read_csv(path)

    dramas_df = pd.DataFrame(
        {
            "drama_id": (
                pd.to_numeric(raw_df.get("id", pd.Series(dtype=float)), errors="coerce")
                .fillna(0)
                .astype(int)
            ),
            "title": raw_df.get("titre", raw_df.get("title", "")),
            "synopsis": raw_df.get("synopsis", ""),
            "genres": raw_df.get("genres", ""),
            "note_moyenne": pd.to_numeric(
                raw_df.get("note_moyenne", pd.Series(dtype=float)),
                errors="coerce",
            ),
            "nb_votes": pd.to_numeric(
                raw_df.get("nb_votes", pd.Series(dtype=float)),
                errors="coerce",
            ),
            "date_diffusion": raw_df.get("date_diffusion", pd.Series(dtype=object)),
            "nb_episodes": pd.to_numeric(
                raw_df.get("nb_episodes", pd.Series(dtype=float)),
                errors="coerce",
            ),
            "nb_saisons": pd.to_numeric(
                raw_df.get("nb_saisons", pd.Series(dtype=float)),
                errors="coerce",
            ),
            "reseaux_diffusion": raw_df.get(
                "reseaux_diffusion", pd.Series(dtype=object)
            ),
            "acteurs": raw_df.get("acteurs", pd.Series(dtype=object)),
            "tags": raw_df.get("tags", pd.Series(dtype=object)),
            "poster": raw_df.get("poster", raw_df.get("affiche", "")),
            "ending_type": raw_df.get("ending_type", "unknown"),
            "sentiment_score": pd.to_numeric(
                raw_df.get("sentiment_score", pd.Series(dtype=float)),
                errors="coerce",
            ).fillna(0.0),
            "top_comments": raw_df.get("top_comments", ""),
            "viewer_consensus": raw_df.get("viewer_consensus", ""),
            "sentiment_summary": raw_df.get("sentiment_summary", ""),
            "principal_actors": raw_df.get(
                "principal_actors",
                raw_df.get("acteurs", pd.Series(dtype=object)),
            ),
        }
    )

    dramas_df["title"] = dramas_df["title"].fillna("").astype(str)
    dramas_df = dramas_df[dramas_df["title"].str.strip() != ""].reset_index(drop=True)
    if dramas_df.empty:
        logger.warning("Local snapshot is empty after cleaning: %s", path)
        return _load_embedded_catalog()

    if (dramas_df["drama_id"] <= 0).all():
        dramas_df["drama_id"] = list(range(1, len(dramas_df) + 1))
    else:
        zero_mask = dramas_df["drama_id"] <= 0
        if zero_mask.any():
            replacement_ids = range(1, zero_mask.sum() + 1)
            dramas_df.loc[zero_mask, "drama_id"] = list(replacement_ids)

    dramas_df["synopsis"] = dramas_df["synopsis"].fillna("")
    dramas_df["genres"] = dramas_df["genres"].fillna("")
    dramas_df["principal_actors"] = dramas_df["principal_actors"].fillna("")
    dramas_df["ending_type"] = dramas_df["ending_type"].fillna("unknown")

    logger.info("Catalogue chargé depuis snapshot local: %s (%d K-Dramas)", path, len(dramas_df))
    return dramas_df


def _get_database_url() -> str:
    url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Database connection is not configured. "
            "Set SUPABASE_DB_URL or DATABASE_URL in your .env file."
        )
    return url


def _result_to_frame(result: Any) -> pd.DataFrame:
    rows = result.fetchall()
    return pd.DataFrame([dict(zip(result.keys(), row)) for row in rows])


def load_dramas_from_etape1(db_url: str | None = None) -> pd.DataFrame:
    if _is_env_true("USE_LOCAL_DATA_SNAPSHOT", default=False):
        return _load_dramas_from_snapshot()

    allow_fallback_on_error = _is_env_true(
        "FALLBACK_TO_LOCAL_ON_DB_ERROR", default=False
    )

    try:
        url = db_url or _get_database_url()
    except RuntimeError as exc:
        if allow_fallback_on_error:
            logger.warning("DB URL unavailable, fallback snapshot activé: %s", exc)
            return _load_dramas_from_snapshot()
        raise

    engine = create_engine(url, pool_pre_ping=True)

    query = text(
        """
        SELECT
            kd.id AS drama_id,
            kd.titre AS title,
            kd.synopsis,
            COALESCE(NULLIF(kd.genres, ''), genre_data.genre_names, '') AS genres,
            kd.note_moyenne,
            kd.nb_votes,
            kd.date_diffusion,
            kd.nb_episodes,
            kd.nb_saisons,
            kd.reseaux_diffusion,
            kd.acteurs,
            kd.tags,
            kd.poster,
            COALESCE(ds.ending_type, 'unknown') AS ending_type,
            COALESCE(ds.sentiment_score, 0.0) AS sentiment_score,
            COALESCE(ds.top_comments, '') AS top_comments,
            COALESCE(ds.viewer_consensus, '') AS viewer_consensus,
            COALESCE(ds.sentiment_summary, '') AS sentiment_summary,
            COALESCE(actor_data.principal_actors, '') AS principal_actors
        FROM kdrama.kdramas kd
        LEFT JOIN (
            SELECT
                kg.kdrama_id,
                STRING_AGG(g.nom, ', ' ORDER BY g.nom) AS genre_names
            FROM kdrama.kdrama_genres kg
            JOIN kdrama.genres g ON g.id = kg.genre_id
            GROUP BY kg.kdrama_id
        ) AS genre_data
            ON genre_data.kdrama_id = kd.id
        LEFT JOIN (
            SELECT
                ka.kdrama_id,
                STRING_AGG(a.nom, ', ' ORDER BY a.nom) AS principal_actors
            FROM kdrama.kdrama_acteurs ka
            JOIN kdrama.acteurs a ON a.id = ka.acteur_id
            WHERE COALESCE(ka.role_principal, FALSE) = TRUE
            GROUP BY ka.kdrama_id
        ) AS actor_data
            ON actor_data.kdrama_id = kd.id
        LEFT JOIN kdrama.drama_sentiments ds
            ON ds.drama_id = kd.id
        WHERE kd.titre IS NOT NULL
        ORDER BY kd.titre
        """
    )

    try:
        with engine.connect() as conn:
            dramas_df = _result_to_frame(conn.execute(query))
    except Exception as exc:
        if allow_fallback_on_error:
            logger.warning("DB inaccessible, fallback snapshot activé: %s", exc)
            return _load_dramas_from_snapshot()
        raise RuntimeError(f"Error reading the kdramas table: {exc}") from exc
    finally:
        engine.dispose()

    if dramas_df.empty:
        if allow_fallback_on_error:
            logger.warning("Table kdramas vide, fallback snapshot activé")
            return _load_dramas_from_snapshot()
        raise RuntimeError("The kdramas table is empty.")

    dramas_df["synopsis"] = dramas_df["synopsis"].fillna("")
    dramas_df["genres"] = dramas_df["genres"].fillna("")
    dramas_df["principal_actors"] = dramas_df["principal_actors"].fillna("")
    dramas_df["ending_type"] = dramas_df["ending_type"].fillna("unknown")
    dramas_df["viewer_consensus"] = dramas_df["viewer_consensus"].fillna("")
    dramas_df["top_comments"] = dramas_df["top_comments"].fillna("")
    dramas_df["sentiment_summary"] = dramas_df["sentiment_summary"].fillna("")
    dramas_df["sentiment_score"] = pd.to_numeric(
        dramas_df["sentiment_score"], errors="coerce"
    ).fillna(0.0)

    # kdrama.kdrama_acteurs / kdrama.acteurs are not populated by the current
    # collection pipeline, so actor_data.principal_actors above is always
    # empty. The real actor data lives in kdramas.acteurs (JSON), so derive
    # principal actors from there whenever the SQL join came back blank.
    needs_actor_fallback = dramas_df["principal_actors"].astype(str).str.strip() == ""
    if needs_actor_fallback.any():
        dramas_df.loc[needs_actor_fallback, "principal_actors"] = dramas_df.loc[
            needs_actor_fallback, "acteurs"
        ].apply(_extract_principal_actors_from_json)

    try:
        review_snippets = _load_review_snippets(engine_url=db_url or _get_database_url())
        dramas_df["review_snippet"] = dramas_df["drama_id"].map(review_snippets).fillna("")
    except Exception as exc:
        logger.warning("Impossible de charger les extraits de drama_reviews : %s", exc)
        dramas_df["review_snippet"] = ""

    logger.info(
        "Catalogue chargé depuis l'étape 1 (PostgreSQL) : %d K-Dramas",
        len(dramas_df),
    )
    return dramas_df


def _extract_principal_actors_from_json(raw_acteurs: Any, max_actors: int = 5) -> str:
    """Derives a comma-separated list of principal actor names from the raw
    kdramas.acteurs JSON column (used as a fallback since kdrama.acteurs /
    kdrama.kdrama_acteurs are not populated by the current pipeline).
    """
    if not raw_acteurs or not isinstance(raw_acteurs, str):
        return ""
    try:
        entries = json.loads(raw_acteurs)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(entries, list):
        return ""

    names = [
        str(entry.get("nom", "")).strip()
        for entry in entries
        if isinstance(entry, dict) and entry.get("role_principal") and entry.get("nom")
    ]
    if not names:
        names = [
            str(entry.get("nom", "")).strip()
            for entry in entries
            if isinstance(entry, dict) and entry.get("nom")
        ][:max_actors]
    return ", ".join(name for name in names if name)


_REVIEW_BOILERPLATE_RE = re.compile(
    r"^.*?Rewatch Value\s+[\d.]+\s*(?:This review may contain spoilers\s*)?",
    re.DOTALL | re.IGNORECASE,
)


def _clean_review_snippet(raw_text: str, max_chars: int = 350) -> str:
    """Strips the MyDramaList review boilerplate header (username, helpful
    count, per-category ratings, spoiler notice) and truncates to a short
    snippet suitable for enriching the model's semantic content text.
    """
    if not raw_text:
        return ""
    cleaned = _REVIEW_BOILERPLATE_RE.sub("", raw_text, count=1).strip()
    if not cleaned:
        cleaned = raw_text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "…"


def _load_review_snippets(engine_url: str) -> dict[int, str]:
    """Loads one representative (longest) real viewer review per drama from
    kdrama.drama_reviews (~22k real MyDramaList reviews, currently unused by
    the model) to enrich semantic matching beyond the short synopsis — e.g.
    a query like "island" can match a review mentioning the setting even
    when the synopsis itself doesn't.
    """
    engine = create_engine(engine_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT DISTINCT ON (drama_id) drama_id, review_text
                    FROM kdrama.drama_reviews
                    WHERE review_text IS NOT NULL AND LENGTH(review_text) > 200
                    ORDER BY drama_id, LENGTH(review_text) DESC
                    """
                )
            )
            rows = result.fetchall()
    finally:
        engine.dispose()

    return {
        int(drama_id): _clean_review_snippet(review_text)
        for drama_id, review_text in rows
    }


def generate_interactions_from_catalog(
    dramas_df: pd.DataFrame,
    num_users: int = 50,
    avg_interactions_per_user: int = 8,
    noise_std: float = 1.0,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    rng = np.random.RandomState(random_state)

    if "note_moyenne" not in dramas_df.columns:
        raise ValueError(
            "dramas_df must contain the 'note_moyenne' column "
            "(real aggregated ratings from step 1)."
        )

    drama_ids = dramas_df["drama_id"].tolist()
    mean_scores = dramas_df["note_moyenne"].fillna(7.0).tolist()

    interactions_data: list[dict[str, Any]] = []
    for user_id in range(1, num_users + 1):
        n_interactions = max(1, int(rng.poisson(avg_interactions_per_user)))
        n_interactions = min(n_interactions, len(drama_ids))
        chosen_indices = rng.choice(len(drama_ids), size=n_interactions, replace=False)

        for idx in chosen_indices:
            base_score = float(mean_scores[idx])
            noisy_score = base_score + rng.normal(0, noise_std)
            rating = float(np.clip(round(noisy_score, 1), 1.0, 10.0))
            interactions_data.append(
                {
                    "user_id": user_id,
                    "drama_id": int(drama_ids[idx]),
                    "rating": rating,
                }
            )

    interactions_df = pd.DataFrame(interactions_data)
    interactions_df = interactions_df.drop_duplicates(
        subset=["user_id", "drama_id"]
    ).reset_index(drop=True)

    logger.info(
        "Interactions synthétiques générées : %d utilisateurs, %d notes.",
        interactions_df["user_id"].nunique(),
        len(interactions_df),
    )
    return interactions_df


def _history_rating(row: pd.Series) -> float:
    status_value = str(row.get("statut", "")).strip().lower()
    episodes_seen = pd.to_numeric(row.get("episodes_vus", 0), errors="coerce")
    episodes_seen = float(episodes_seen) if pd.notna(episodes_seen) else 0.0

    if status_value == "termine":
        return 8.8
    if status_value == "en_cours":
        return float(np.clip(6.4 + min(episodes_seen, 16.0) * 0.15, 1.0, 8.6))
    if status_value == "abandonne":
        return 2.0
    if status_value == "a_voir":
        return 6.0
    return 5.5


def load_real_interactions_from_etape1(db_url: str | None = None) -> pd.DataFrame:
    url = db_url or _get_database_url()
    engine = create_engine(url, pool_pre_ping=True)

    queries = {
        "notes": text(
            """
            SELECT utilisateur_id AS user_id, kdrama_id AS drama_id, note
            FROM kdrama.notes
            WHERE utilisateur_id IS NOT NULL AND kdrama_id IS NOT NULL AND note IS NOT NULL
            """
        ),
        "historique": text(
            """
            SELECT utilisateur_id AS user_id, kdrama_id AS drama_id, episodes_vus, statut
            FROM kdrama.historique_visionnage
            WHERE utilisateur_id IS NOT NULL AND kdrama_id IS NOT NULL
            """
        ),
        "favoris": text(
            """
            SELECT utilisateur_id AS user_id, kdrama_id AS drama_id
            FROM kdrama.favoris
            WHERE utilisateur_id IS NOT NULL AND kdrama_id IS NOT NULL
            """
        ),
        "interets": text(
            """
            SELECT utilisateur_id AS user_id, kdrama_id AS drama_id, interesse
            FROM kdrama.interet_utilisateur
            WHERE utilisateur_id IS NOT NULL AND kdrama_id IS NOT NULL
            """
        ),
    }

    try:
        with engine.connect() as conn:
            notes_df = _result_to_frame(conn.execute(queries["notes"]))
            history_df = _result_to_frame(conn.execute(queries["historique"]))
            favorites_df = _result_to_frame(conn.execute(queries["favoris"]))
            interests_df = _result_to_frame(conn.execute(queries["interets"]))
    finally:
        engine.dispose()

    frames: list[pd.DataFrame] = []

    if not notes_df.empty:
        notes = notes_df.copy()
        notes["rating"] = pd.to_numeric(notes["note"], errors="coerce").clip(1.0, 10.0)
        notes["signal_weight"] = 1.0
        frames.append(notes[["user_id", "drama_id", "rating", "signal_weight"]])

    if not history_df.empty:
        history = history_df.copy()
        history["rating"] = history.apply(_history_rating, axis=1)
        history["signal_weight"] = history["statut"].astype(str).str.lower().map(
            {
                "termine": 1.1,
                "en_cours": 0.8,
                "a_voir": 0.6,
                "abandonne": 1.1,
            }
        ).fillna(0.7)
        frames.append(history[["user_id", "drama_id", "rating", "signal_weight"]])

    if not favorites_df.empty:
        favorites = favorites_df.copy()
        favorites["rating"] = 9.8
        favorites["signal_weight"] = 1.6
        frames.append(favorites[["user_id", "drama_id", "rating", "signal_weight"]])

    if not interests_df.empty:
        interests = interests_df.copy()
        interests["rating"] = interests["interesse"].apply(
            lambda value: 9.2 if bool(value) else 1.0
        )
        interests["signal_weight"] = interests["interesse"].apply(
            lambda value: 1.4 if bool(value) else 1.6
        )
        frames.append(interests[["user_id", "drama_id", "rating", "signal_weight"]])

    if not frames:
        return pd.DataFrame(columns=["user_id", "drama_id", "rating"])

    interactions_df = pd.concat(frames, ignore_index=True)
    interactions_df = interactions_df.dropna(subset=["user_id", "drama_id", "rating"])
    interactions_df["user_id"] = pd.to_numeric(
        interactions_df["user_id"], errors="coerce"
    )
    interactions_df["drama_id"] = pd.to_numeric(
        interactions_df["drama_id"], errors="coerce"
    )
    interactions_df = interactions_df.dropna(subset=["user_id", "drama_id"])
    interactions_df["user_id"] = interactions_df["user_id"].astype(int)
    interactions_df["drama_id"] = interactions_df["drama_id"].astype(int)

    aggregated = (
        interactions_df.assign(
            weighted_rating=interactions_df["rating"] * interactions_df["signal_weight"]
        )
        .groupby(["user_id", "drama_id"], as_index=False)
        .agg(
            weighted_rating=("weighted_rating", "sum"),
            weight_total=("signal_weight", "sum"),
        )
    )
    aggregated["rating"] = (
        aggregated["weighted_rating"] / aggregated["weight_total"]
    ).clip(1.0, 10.0)
    aggregated = aggregated[["user_id", "drama_id", "rating"]].sort_values(
        ["user_id", "drama_id"]
    )
    aggregated = aggregated.reset_index(drop=True)

    logger.info(
        "Interactions réelles chargées : %d utilisateurs, %d interactions agrégées.",
        aggregated["user_id"].nunique() if not aggregated.empty else 0,
        len(aggregated),
    )
    return aggregated


def empty_user_preferences(user_id: int | None = None) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "favorite_genres": [],
        "favorite_actors": [],
        "happy_ending_only": False,
        "favorite_drama_ids": [],
        "interested_drama_ids": [],
        "disliked_drama_ids": [],
    }


# Short-lived in-process cache for fetch_user_preferences(): recommendation
# preferences (favorite genres/actors, happy-ending flag, favorites, interest
# feedback) change far less often than a /recommend request is made, so a
# small TTL cache avoids a full DB round-trip (5 queries over the network to
# the remote Supabase pooler) on every single request for the same user.
_USER_PREFERENCES_CACHE: dict[int, tuple[float, dict[str, Any]]] = {}
_USER_PREFERENCES_CACHE_TTL_SECONDS = 30.0


def fetch_user_preferences(user_id: int, db_url: str | None = None) -> dict[str, Any]:
    now = time.monotonic()
    cached = _USER_PREFERENCES_CACHE.get(user_id)
    if cached is not None and (now - cached[0]) < _USER_PREFERENCES_CACHE_TTL_SECONDS:
        return cached[1]

    preferences = empty_user_preferences(user_id)
    if user_id <= 0 or _is_env_true("USE_LOCAL_DATA_SNAPSHOT", default=False):
        return preferences

    try:
        url = db_url or _get_database_url()
    except RuntimeError as exc:
        logger.warning("Impossible de charger les préférences utilisateur %s: %s", user_id, exc)
        return preferences

    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            user_df = _result_to_frame(
                conn.execute(
                    text(
                        """
                        SELECT fin_heureuse_uniquement
                        FROM kdrama.utilisateurs
                        WHERE id = :user_id
                        """
                    ),
                    {"user_id": user_id},
                )
            )
            genres_df = _result_to_frame(
                conn.execute(
                    text(
                        """
                        SELECT g.nom AS genre_name
                        FROM kdrama.utilisateur_genres_preferes ugp
                        JOIN kdrama.genres g ON g.id = ugp.genre_id
                        WHERE ugp.utilisateur_id = :user_id
                        ORDER BY g.nom
                        """
                    ),
                    {"user_id": user_id},
                )
            )
            actors_df = _result_to_frame(
                conn.execute(
                    text(
                        """
                        SELECT acteur_nom AS actor_name
                        FROM kdrama.utilisateur_acteurs_preferes
                        WHERE utilisateur_id = :user_id
                        ORDER BY acteur_nom
                        """
                    ),
                    {"user_id": user_id},
                )
            )
            favorites_df = _result_to_frame(
                conn.execute(
                    text(
                        """
                        SELECT kdrama_id AS drama_id
                        FROM kdrama.favoris
                        WHERE utilisateur_id = :user_id
                        ORDER BY kdrama_id
                        """
                    ),
                    {"user_id": user_id},
                )
            )
            interests_df = _result_to_frame(
                conn.execute(
                    text(
                        """
                        SELECT kdrama_id AS drama_id, interesse
                        FROM kdrama.interet_utilisateur
                        WHERE utilisateur_id = :user_id
                        ORDER BY kdrama_id
                        """
                    ),
                    {"user_id": user_id},
                )
            )
    except Exception as exc:
        logger.warning("Erreur chargement préférences utilisateur %s: %s", user_id, exc)
        return preferences
    finally:
        engine.dispose()

    if not user_df.empty:
        preferences["happy_ending_only"] = bool(
            user_df.iloc[0].get("fin_heureuse_uniquement", False)
        )

    preferences["favorite_genres"] = [
        genre
        for genre in genres_df.get("genre_name", pd.Series(dtype=object)).astype(str).tolist()
        if genre and genre.lower() != "nan"
    ]
    preferences["favorite_actors"] = [
        actor
        for actor in actors_df.get("actor_name", pd.Series(dtype=object)).astype(str).tolist()
        if actor and actor.lower() != "nan"
    ]
    preferences["favorite_drama_ids"] = [
        int(drama_id)
        for drama_id in favorites_df.get("drama_id", pd.Series(dtype=float)).dropna().tolist()
    ]

    if not interests_df.empty:
        positive = interests_df[interests_df["interesse"].astype(bool)]
        negative = interests_df[~interests_df["interesse"].astype(bool)]
        preferences["interested_drama_ids"] = [
            int(drama_id)
            for drama_id in positive.get("drama_id", pd.Series(dtype=float)).dropna().tolist()
        ]
        preferences["disliked_drama_ids"] = [
            int(drama_id)
            for drama_id in negative.get("drama_id", pd.Series(dtype=float)).dropna().tolist()
        ]

    _USER_PREFERENCES_CACHE[user_id] = (now, preferences)
    return preferences


def load_real_data(
    db_url: str | None = None,
    num_users: int = 50,
    avg_interactions_per_user: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dramas_df = load_dramas_from_etape1(db_url)

    try:
        interactions_df = load_real_interactions_from_etape1(db_url)
        if len(interactions_df) < MIN_REAL_INTERACTIONS:
            logger.warning(
                "Seulement %d interactions réelles détectées (< %d). "
                "Fallback vers le générateur synthétique.",
                len(interactions_df),
                MIN_REAL_INTERACTIONS,
            )
            interactions_df = generate_interactions_from_catalog(
                dramas_df,
                num_users=num_users,
                avg_interactions_per_user=avg_interactions_per_user,
            )
    except Exception as exc:
        logger.warning(
            "Chargement des interactions réelles impossible (%s). "
            "Fallback vers le générateur synthétique.",
            exc,
        )
        interactions_df = generate_interactions_from_catalog(
            dramas_df,
            num_users=num_users,
            avg_interactions_per_user=avg_interactions_per_user,
        )

    return dramas_df, interactions_df
