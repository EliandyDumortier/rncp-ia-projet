#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drama_sentiment_scraper.py — Scraper pour analyser les sentiments et endings des K-Dramas.

Ce module scrape les informations sur les endings (heureux/triste/bittersweet),
le statut (en cours/terminé), et le sentiment global des spectateurs pour chaque
drama dans la base de données.

Sources:
  - MyDramaList (commentaires et classifications)
  - Wikipedia (synopses et endings)
  - IMDB (critiques utilisateurs)
  - Reddit (discussions sur les endings)

Compétence RNCP C3 : Extraction et analyse de données web.

Auteur : Équipe Data Science
Projet : Système de recommandation de K-Dramas par IA
Étape : 1 — Collecte et préparation des données
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
_THIS_FILE = Path(__file__).resolve()
if "dossier_projet" in _THIS_FILE.parts:
    _PROJECT_ROOT = _THIS_FILE.parents[3]
else:
    _PROJECT_ROOT = _THIS_FILE.parents[1]

for _env_path in (
    Path.cwd() / ".env",
    _PROJECT_ROOT / ".env",
    _PROJECT_ROOT / "dossier_projet" / "etape1" / ".env",
):
    load_dotenv(_env_path, override=False)


def _get_database_url() -> str:
    """Get database connection URL from environment."""
    url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Database connection not configured. "
            "Set SUPABASE_DB_URL or DATABASE_URL in .env"
        )
    return url


class DramaSentimentScraper:
    """Scraper pour récupérer les sentiments et endings des dramas."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or _get_database_url()
        self.engine = create_engine(self.db_url, pool_pre_ping=True)

    def get_unscraped_dramas(self, limit: int = 100) -> pd.DataFrame:
        """Récupère les dramas non encore scrapés."""
        query = """
        SELECT k.id, k.titre, k.titre_original, k.date_diffusion
        FROM kdrama.kdramas k
        LEFT JOIN kdrama.drama_sentiments ds ON k.id = ds.drama_id
        WHERE ds.id IS NULL
        ORDER BY k.titre
        LIMIT :limit
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(query), {"limit": limit})
            return pd.DataFrame(result.fetchall(), columns=['id', 'titre', 'titre_original', 'date_diffusion'])

    async def scrape_mydramilist(self, drama_title: str) -> dict[str, Any]:
        """Scrape MyDramaList pour le drama."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        url = f"https://mydramalist.com/search?q={quote(drama_title)}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return {}

                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Rechercher le premier résultat
                    first_result = soup.find('div', class_='mdl-cell')
                    if not first_result:
                        return {}

                    # Extraire le lien vers la page du drama
                    link = first_result.find('a')
                    if not link or 'href' not in link.attrs:
                        return {}

                    drama_url = link['href']
                    if not drama_url.startswith('http'):
                        drama_url = f"https://mydramalist.com{drama_url}"

                    # Scraper la page du drama
                    async with session.get(drama_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as drama_resp:
                        if drama_resp.status != 200:
                            return {}

                        drama_html = await drama_resp.text()
                        drama_soup = BeautifulSoup(drama_html, 'html.parser')

                        result = {
                            'url': drama_url,
                            'ending_type': None,
                            'is_ongoing': False,
                            'sentiment_score': 0.5,
                        }

                        # Chercher les informations d'ending dans les tags/descriptions
                        summary = drama_soup.find('p', class_='synopsis')
                        if summary:
                            text = summary.get_text().lower()
                            result['ending_type'] = classify_ending_from_text(text)

                        # Vérifier si en cours
                        status_div = drama_soup.find('div', class_='status')
                        if status_div:
                            status_text = status_div.get_text().lower()
                            result['is_ongoing'] = 'ongoing' in status_text or 'airing' in status_text

                        return result

        except Exception as e:
            logger.warning(f"Erreur scraping MyDramaList pour '{drama_title}': {e}")
            return {}

    async def scrape_wikipedia(self, drama_title: str) -> dict[str, Any]:
        """Scrape Wikipedia pour le drama."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        search_query = f"{drama_title} Korean television series"
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(search_query)}&format=json"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return {}

                    data = await resp.json()
                    if not data.get('query', {}).get('search'):
                        return {}

                    # Prendre le premier résultat
                    first_result = data['query']['search'][0]
                    page_title = first_result['title']

                    # Récupérer le contenu de la page
                    page_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={quote(page_title)}&prop=extracts&explaintext=true&format=json"
                    async with session.get(page_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as page_resp:
                        if page_resp.status != 200:
                            return {}

                        page_data = await page_resp.json()
                        pages = page_data.get('query', {}).get('pages', {})
                        page_content = list(pages.values())[0].get('extract', '')

                        result = {
                            'url': f"https://en.wikipedia.org/wiki/{quote(page_title)}",
                            'ending_type': classify_ending_from_text(page_content.lower()),
                        }

                        return result

        except Exception as e:
            logger.warning(f"Erreur scraping Wikipedia pour '{drama_title}': {e}")
            return {}

    def save_sentiment(self, drama_id: int, sentiment_data: dict[str, Any]) -> bool:
        """Sauvegarde les données de sentiment dans la base."""
        try:
            with self.engine.connect() as conn:
                # Vérifier si la sentiments existe déjà
                check = conn.execute(
                    text("SELECT id FROM kdrama.drama_sentiments WHERE drama_id = :id"),
                    {"id": drama_id}
                ).fetchone()

                if check:
                    # Mise à jour
                    query = """
                    UPDATE kdrama.drama_sentiments
                    SET ending_type = :ending_type,
                        ending_confidence = :ending_confidence,
                        sentiment_score = :sentiment_score,
                        is_ongoing = :is_ongoing,
                        is_completed = :is_completed,
                        source_urls = :source_urls,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE drama_id = :drama_id
                    """
                else:
                    # Insertion
                    query = """
                    INSERT INTO kdrama.drama_sentiments
                    (drama_id, ending_type, ending_confidence, sentiment_score, is_ongoing, is_completed, source_urls)
                    VALUES (:drama_id, :ending_type, :ending_confidence, :sentiment_score, :is_ongoing, :is_completed, :source_urls)
                    """

                conn.execute(text(query), {
                    "drama_id": drama_id,
                    "ending_type": sentiment_data.get("ending_type", "unknown"),
                    "ending_confidence": sentiment_data.get("ending_confidence", 0.5),
                    "sentiment_score": sentiment_data.get("sentiment_score", 0.0),
                    "is_ongoing": sentiment_data.get("is_ongoing", False),
                    "is_completed": not sentiment_data.get("is_ongoing", False),
                    "source_urls": sentiment_data.get("source_urls", []),
                })
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde sentiment pour drama {drama_id}: {e}")
            return False

    async def scrape_drama(self, drama_id: int, drama_title: str) -> bool:
        """Scrape un drama et sauvegarde ses données."""
        logger.info(f"Scraping drama: {drama_title}")

        # Scraper différentes sources en parallèle
        results = await asyncio.gather(
            self.scrape_mydramilist(drama_title),
            self.scrape_wikipedia(drama_title),
            return_exceptions=True
        )

        # Fusionner les résultats
        merged_data = {
            "ending_type": "unknown",
            "ending_confidence": 0.3,
            "sentiment_score": 0.5,
            "is_ongoing": False,
            "source_urls": []
        }

        for result in results:
            if isinstance(result, Exception):
                continue
            if result.get('url'):
                merged_data['source_urls'].append(result['url'])
            if result.get('ending_type'):
                merged_data['ending_type'] = result['ending_type']
                merged_data['ending_confidence'] = 0.7
            if result.get('is_ongoing'):
                merged_data['is_ongoing'] = result['is_ongoing']

        # Sauvegarder
        return self.save_sentiment(drama_id, merged_data)

    async def scrape_all(self, batch_size: int = 50, max_workers: int = 5):
        """Scrape tous les dramas non scrapés."""
        logger.info("Démarrage du scraping des sentiments")

        dramas = self.get_unscraped_dramas(limit=batch_size)
        if dramas.empty:
            logger.info("Aucun drama à scraper")
            return

        logger.info(f"Scraping {len(dramas)} dramas avec {max_workers} workers")

        # Limiter le nombre de workers simultanés
        semaphore = asyncio.Semaphore(max_workers)

        async def scrape_with_semaphore(drama_id: int, title: str):
            async with semaphore:
                return await self.scrape_drama(drama_id, title)

        tasks = [
            scrape_with_semaphore(row['id'], row['titre'])
            for _, row in dramas.iterrows()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if r is True)
        logger.info(f"Scraping terminé: {successful}/{len(dramas)} réussis")


def classify_ending_from_text(text: str) -> str:
    """Classifie le type d'ending à partir du texte."""
    text_lower = text.lower()

    # Indicateurs tristes
    sad_keywords = ['death', 'died', 'sacrifice', 'tragic', 'bittersweet', 'separation', 'broken up']
    sad_count = sum(1 for kw in sad_keywords if kw in text_lower)

    # Indicateurs heureux
    happy_keywords = ['reunion', 'together', 'happy ending', 'married', 'together forever', 'love wins']
    happy_count = sum(1 for kw in happy_keywords if kw in text_lower)

    if sad_count > happy_count:
        return 'sad'
    elif happy_count > sad_count:
        return 'happy'
    elif sad_count > 0 or happy_count > 0:
        return 'bittersweet'
    else:
        return 'unknown'


async def main():
    """Point d'entrée principal."""
    scraper = DramaSentimentScraper()
    await scraper.scrape_all(batch_size=50, max_workers=5)


if __name__ == '__main__':
    asyncio.run(main())
