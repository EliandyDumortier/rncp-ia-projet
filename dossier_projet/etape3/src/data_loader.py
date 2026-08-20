#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_loader.py — Chargement des données réelles depuis l'étape 1.

Ce module remplace les données synthétiques (generate_sample_data) par
les vraies données collectées à l'étape 1 :
  - Le catalogue de K-Dramas est lu depuis la base PostgreSQL Supabase
    (table « kdramas ») créée à l'étape 1. La connexion utilise
    SUPABASE_DB_URL ou DATABASE_URL du fichier .env.
  - Les notes par utilisateur sont générées de façon déterministe à
    partir de la note moyenne réelle de chaque drama (note_moyenne).
    Comme l'étape 1 ne contient que des scores agrégés (pas de notes
    individuelles par utilisateur), on simule des notes individuelles
    centrées sur la note moyenne réelle, avec un bruit contrôlé.

Compétence RNCP C3 : Utilisation de données réelles du pipeline.

Auteur : Équipe Data Science
Projet : Système de recommandation de K-Dramas par IA
Étape : 3 — Modélisation et MLOps
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# Charge les variables de l'étape 1 lorsque le script est lancé depuis l'étape 3.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
for _env_path in (
    Path.cwd() / ".env",
    _PROJECT_ROOT / ".env",
    _PROJECT_ROOT / "dossier_projet" / "etape3" / ".env",
    _PROJECT_ROOT / "dossier_projet" / "etape1" / ".env",
):
    load_dotenv(_env_path, override=False)

# Graine aléatoire pour la reproductibilité
RANDOM_STATE = 42


def _get_database_url() -> str:
    """Récupère l'URL de connexion PostgreSQL depuis les variables d'environnement.

    Ordre de priorité :
        1. SUPABASE_DB_URL (variable Supabase pré-configurée)
        2. DATABASE_URL (variable générique)

    Returns:
        URL de connexion PostgreSQL.

    Raises:
        RuntimeError: Si aucune variable d'environnement n'est définie.
    """
    url = os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Database connection is not configured. "
            "Set SUPABASE_DB_URL or DATABASE_URL in your .env file."
        )
    return url


def load_dramas_from_etape1(db_url: str | None = None) -> pd.DataFrame:
    """
    Charge le catalogue de K-Dramas depuis la base PostgreSQL de l'étape 1.

    Lit la table « kdramas » (schéma public) et retourne un DataFrame au
    format attendu par HybridRecommender.train() :
        ['drama_id', 'title', 'synopsis', 'genres', 'note_moyenne', ...]

    Args:
        db_url: URL de connexion PostgreSQL. Si None, lit depuis les
                variables d'environnement (SUPABASE_DB_URL ou DATABASE_URL).

    Returns:
        DataFrame contenant le catalogue réel de K-Dramas.

    Raises:
        RuntimeError: Si la table kdramas est vide ou introuvable.
    """
    url = db_url or _get_database_url()
    engine = create_engine(url, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY titre) AS drama_id,
                        titre AS title,
                        synopsis,
                        genres,
                        note_moyenne,
                        nb_votes,
                        date_diffusion,
                        reseaux_diffusion,
                        acteurs,
                        tags
                    FROM kdramas
                    WHERE titre IS NOT NULL
                    ORDER BY titre
                    """
                )
            )
            rows = result.fetchall()
    except Exception as exc:
        raise RuntimeError(
            f"Error reading the kdramas table: {exc}"
        ) from exc
    finally:
        engine.dispose()

    if not rows:
        raise RuntimeError("The kdramas table is empty.")

    columns = list(result.keys())
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(dict(zip(columns, row)))

    dramas_df = pd.DataFrame(records)

    # Nettoyage : remplir les synopsis et genres manquants
    dramas_df["synopsis"] = dramas_df["synopsis"].fillna("")
    dramas_df["genres"] = dramas_df["genres"].fillna("")

    logger.info(
        "Catalogue chargé depuis l'étape 1 (PostgreSQL) : %d K-Dramas",
        len(dramas_df),
    )
    return dramas_df


def generate_interactions_from_catalog(
    dramas_df: pd.DataFrame,
    num_users: int = 50,
    avg_interactions_per_user: int = 8,
    noise_std: float = 1.0,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """
    Génère des notes individuelles par utilisateur à partir du catalogue réel.

    Comme l'étape 1 ne contient que des scores agrégés (note_moyenne par
    drama, pas de notes individuelles), on simule des notes individuelles
    centrées sur la note moyenne réelle de chaque drama. Le bruit est
    contrôlé pour rester dans [1, 10].

    Args:
        dramas_df: DataFrame du catalogue (doit contenir 'drama_id' et
                   'note_moyenne').
        num_users: Nombre d'utilisateurs simulés.
        avg_interactions_per_user: Nombre moyen de dramas notés par
                                   utilisateur.
        noise_std: Écart-type du bruit gaussien ajouté à la note moyenne.
        random_state: Graine pour la reproductibilité.

    Returns:
        DataFrame avec colonnes ['user_id', 'drama_id', 'rating'].
    """
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
        n_interactions = max(
            1,
            int(rng.poisson(avg_interactions_per_user)),
        )
        n_interactions = min(n_interactions, len(drama_ids))

        chosen_indices = rng.choice(
            len(drama_ids),
            size=n_interactions,
            replace=False,
        )

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
        "Interactions générées : %d utilisateurs, %d notes "
        "(basées sur les scores agrégés réels de l'étape 1)",
        interactions_df["user_id"].nunique(),
        len(interactions_df),
    )
    return interactions_df


def load_real_data(
    db_url: str | None = None,
    num_users: int = 50,
    avg_interactions_per_user: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Charge les données réelles pour l'entraînement du modèle.

    Workflow :
      1. Charge le catalogue de K-Dramas depuis la base PostgreSQL de
         l'étape 1 (vraies données collectées, 915 K-Dramas).
      2. Génère des notes individuelles par utilisateur, centrées sur
         les notes moyennes réelles de chaque drama.

    Args:
        db_url: URL de connexion PostgreSQL. Si None, lit depuis les
                variables d'environnement.
        num_users: Nombre d'utilisateurs simulés pour le filtrage
                   collaboratif.
        avg_interactions_per_user: Nombre moyen de notes par utilisateur.

    Returns:
        Tuple (dramas_df, interactions_df) au format attendu par
        HybridRecommender.train().
    """
    dramas_df = load_dramas_from_etape1(db_url)
    interactions_df = generate_interactions_from_catalog(
        dramas_df,
        num_users=num_users,
        avg_interactions_per_user=avg_interactions_per_user,
    )
    return dramas_df, interactions_df
