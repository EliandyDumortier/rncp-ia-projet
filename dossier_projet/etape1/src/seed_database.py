"""Seed the local Docker database from the versioned cleaned catalogue.

The import is intentionally idempotent: an existing catalogue is preserved.
User accounts and interaction tables are never modified.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text


DATABASE_URL = os.environ["DATABASE_URL"]
CATALOGUE_PATH = Path("/app/data/clean/kdramas_clean.json")


def clean(value: Any) -> Any:
    """Convert JSON values into PostgreSQL-compatible scalar values."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def clean_date(value: Any) -> date | None:
    value = clean(value)
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def clean_int(value: Any) -> int | None:
    value = clean(value)
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean_country(value: Any) -> str | None:
    if isinstance(value, list):
        value = ",".join(str(item) for item in value)
    value = clean(value)
    return str(value)[:10] if value else None


def main() -> None:
    if not CATALOGUE_PATH.exists():
        raise RuntimeError(f"Versioned catalogue not found: {CATALOGUE_PATH}")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT COUNT(*) FROM kdrama.kdramas")
        ).scalar_one()
        if existing:
            print(f"Catalogue already contains {existing} dramas; seed skipped.")
            return

        records = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
        statement = text(
            """
            INSERT INTO kdrama.kdramas (
                tmdb_id, titre, english_name, titre_original, date_diffusion,
                nb_episodes, nb_saisons, duree_episode, synopsis,
                note_moyenne, nb_votes, langue_originale, pays_origine,
                genres, reseaux_diffusion, poster, source, acteurs, tags,
                rang, popularite, url_source, nb_watchers, realisateur,
                scenariste
            ) VALUES (
                :tmdb_id, :titre, :english_name, :titre_original,
                :date_diffusion, :nb_episodes, :nb_saisons, :duree_episode,
                :synopsis, :note_moyenne, :nb_votes, :langue_originale,
                :pays_origine, :genres, :reseaux_diffusion, :poster, :source,
                :acteurs, :tags, :rang, :popularite, :url_source, :nb_watchers,
                :realisateur, :scenariste
            )
            """
        )

        prepared = []
        for record in records:
            title = clean(record.get("titre") or record.get("english_name"))
            if not title:
                continue
            prepared.append(
                {
                    "tmdb_id": clean_int(record.get("tmdb_id")),
                    "titre": title,
                    "english_name": clean(record.get("english_name")) or title,
                    "titre_original": clean(record.get("titre_original")),
                    "date_diffusion": clean_date(record.get("date_diffusion")),
                    "nb_episodes": clean_int(record.get("nb_episodes")),
                    "nb_saisons": clean_int(record.get("nb_saisons")),
                    "duree_episode": clean_int(record.get("duree_episode")),
                    "synopsis": clean(record.get("synopsis")),
                    "note_moyenne": clean(record.get("note_moyenne")),
                    "nb_votes": clean_int(record.get("nb_votes")),
                    "langue_originale": clean(record.get("langue_originale")),
                    "pays_origine": clean_country(record.get("pays_origine")),
                    "genres": clean(record.get("genres")),
                    "reseaux_diffusion": clean(record.get("reseaux_diffusion")),
                    "poster": clean(record.get("poster")),
                    "source": clean(record.get("source")) or "versioned-catalogue",
                    "acteurs": clean(record.get("acteurs")),
                    "tags": clean(record.get("tags")),
                    "rang": clean_int(record.get("rang")),
                    "popularite": clean(record.get("popularite")),
                    "url_source": clean(record.get("url_source")),
                    "nb_watchers": clean_int(record.get("nb_watchers")),
                    "realisateur": clean(record.get("realisateur")),
                    "scenariste": clean(record.get("scenariste")),
                }
            )

        connection.execute(statement, prepared)
        print(f"Seeded {len(prepared)} real catalogue records.")


if __name__ == "__main__":
    main()
