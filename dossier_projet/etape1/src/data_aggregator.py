#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_aggregator.py — Agrégation, nettoyage et normalisation des données K-Drama.

Ce module implémente le pipeline de traitement des données collectées depuis
quatre sources (TMDB, CSV, MyDramaList, base de données SQLite). Il effectue :
    1. Le chargement des données brutes.
    2. La normalisation des schémas (mapping des champs).
    3. Le nettoyage des chaînes, dates et valeurs numériques.
    4. La suppression des entrées corrompues et des doublons.
    5. La fusion des sources par correspondance de titre.
    6. L'homogénéisation des formats (dates ISO, notes 0-10, genres normalisés).
    7. L'export des données nettoyées (JSON + base PostgreSQL).

Compétence RNCP C3 : Agrégation, nettoyage et normalisation de données.

Auteur : Équipe Data
Projet : Système de recommandation de K-Dramas par IA
Étape : 1 — Collecte et préparation des données
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_aggregator")

# Chargement des variables d'environnement
load_dotenv()

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
CLEAN_DATA_DIR = Path(__file__).parent.parent / "data" / "clean"

# Référentiel des genres normalisés (mapping vers un vocabulaire commun en anglais)
GENRE_NORMALISATION = {
    # Anglais + variantes françaises (sans accents) -> Canonique anglais
    "romance": "Romance",
    "romantic": "Romance",
    "comedy": "Comedy",
    "comedie": "Comedy",
    "comedy romance": "Romantic Comedy",
    "comedie romantique": "Romantic Comedy",
    "thriller": "Thriller",
    "mystery": "Mystery",
    "mystere": "Mystery",
    "historical": "Historical",
    "history": "Historical",
    "historique": "Historical",
    "fantasy": "Fantasy",
    "fantastique": "Fantasy",
    "action": "Action",
    "drama": "Drama",
    "drame": "Drama",
    "melodrama": "Melodrama",
    "melodrame": "Melodrama",
    "crime": "Crime",
    "political": "Political",
    "politique": "Political",
    "medical": "Medical",
    "medicale": "Medical",
    "legal": "Legal",
    "law": "Legal",
    "juridique": "Legal",
    "supernatural": "Supernatural",
    "surnaturel": "Supernatural",
    "horror": "Horror",
    "horreur": "Horror",
    "sci-fi": "Science Fiction",
    "science fiction": "Science Fiction",
    "science-fiction": "Science Fiction",
    "family": "Family",
    "famille": "Family",
    "friendship": "Friendship",
    "amitie": "Friendship",
    "slice of life": "Slice of Life",
    "tranche de vie": "Slice of Life",
    "music": "Music",
    "musique": "Music",
    "sports": "Sports",
    "sport": "Sports",
    "business": "Business",
    "workplace": "Business",
    "youth": "Youth",
    "jeunesse": "Youth",
    "school": "School",
    "ecole": "School",
    "psychological": "Psychological",
    "psychologique": "Psychological",
    "military": "Military",
    "militaire": "Military",
    "espionage": "Espionage",
    "espionnage": "Espionage",
    "zombie": "Zombie",
    "vampire": "Vampire",
    "time travel": "Time Travel",
    "time-travel": "Time Travel",
    "voyage dans le temps": "Time Travel",
}

# Années valides pour les K-Dramas (première diffusion)
ANNEE_MIN = 1990
ANNEE_MAX = datetime.now().year + 1  # Tolérance pour les annonces futures

# Seuil de similarité pour la détection de doublons (0.0 à 1.0)
SEUIL_SIMILARITE_TITRE = 0.90


# ===========================================================================
# Classe de rapport de qualité
# ===========================================================================
@dataclass
class QualityReport:
    """Rapport de qualité des données après traitement.

    Centralise les statistiques du pipeline d'agrégation pour évaluer
    la qualité du jeu de données final.

    Attributes:
        total_brut: Nombre total d'enregistrements bruts (toutes sources).
        total_apres_nettoyage: Nombre d'enregistrements après nettoyage.
        total_apres_fusion: Nombre d'enregistrements après fusion et dédoublonnage.
        doublons_supprimes: Nombre de doublons supprimés.
        valeurs_manquantes: Dictionnaire du nombre de valeurs manquantes par colonne.
        taux_completude: Dictionnaire du taux de complétude par colonne (0-100%).
        par_source: Nombre d'enregistrements par source avant fusion.
    """

    total_brut: int = 0
    total_apres_nettoyage: int = 0
    total_apres_fusion: int = 0
    doublons_supprimes: int = 0
    valeurs_manquantes: dict[str, int] = field(default_factory=dict)
    taux_completude: dict[str, float] = field(default_factory=dict)
    par_source: dict[str, int] = field(default_factory=dict)

    def afficher(self) -> None:
        """Affiche le rapport de qualité dans les logs."""
        logger.info("=" * 60)
        logger.info("RAPPORT DE QUALITÉ DES DONNÉES")
        logger.info("=" * 60)
        logger.info("Total brut (toutes sources): %d", self.total_brut)
        for source, count in self.par_source.items():
            logger.info("  - %s: %d enregistrements", source, count)
        logger.info("Total après nettoyage: %d", self.total_apres_nettoyage)
        logger.info("Total après fusion: %d", self.total_apres_fusion)
        logger.info("Doublons supprimés: %d", self.doublons_supprimes)
        logger.info("--- Complétude par colonne ---")
        for col, taux in sorted(self.taux_completude.items(), key=lambda x: x[1]):
            logger.info("  %s: %.1f%% (%d manquants)", col, taux, self.valeurs_manquantes.get(col, 0))
        logger.info("=" * 60)


# ===========================================================================
# Classe principale d'agrégation
# ===========================================================================
class DataAggregator:
    """Agrégateur et nettoyeur de données K-Drama.

    Pipeline complet de traitement des données :
        1. Chargement des fichiers JSON bruts (TMDB, CSV, MyDramaList).
        2. Normalisation des schémas vers un format commun.
        3. Nettoyage des chaînes, dates, notes et genres.
        4. Suppression des entrées corrompues.
        5. Fusion des sources par correspondance de titre.
        6. Détection et suppression des doublons (similarité floue).
        7. Export vers JSON et base PostgreSQL.

    Attributes:
        raw_dir: Répertoire des données brutes.
        clean_dir: Répertoire des données nettoyées.
        engine: Moteur SQLAlchemy (si export en base).
    """

    def __init__(
        self,
        raw_dir: Path = RAW_DATA_DIR,
        clean_dir: Path = CLEAN_DATA_DIR,
        database_url: Optional[str] = None,
    ) -> None:
        """Initialise l'agrégateur.

        Args:
            raw_dir: Répertoire contenant les fichiers JSON bruts.
            clean_dir: Répertoire de sortie pour les données nettoyées.
            database_url: URL PostgreSQL pour l'export (optionnel).
        """
        self.raw_dir = raw_dir
        self.clean_dir = clean_dir
        self.clean_dir.mkdir(parents=True, exist_ok=True)
        self.engine = None
        if database_url or os.getenv("DATABASE_URL"):
            url = database_url or os.getenv("DATABASE_URL")
            self.engine = create_engine(url, pool_pre_ping=True)
        logger.info("DataAggregator initialisé (raw=%s, clean=%s)", self.raw_dir, self.clean_dir)

    # -------------------------------------------------------------------
    # Étape 1 : Chargement des données brutes
    # -------------------------------------------------------------------

    def load_raw_data(self) -> dict[str, pd.DataFrame]:
        """Charge les fichiers JSON bruts depuis le répertoire de données.

        Lit les fichiers raw_tmdb.json, raw_csv.json et raw_scrape.json
        et les convertit en DataFrames pandas.

        Returns:
            Dictionnaire {source: DataFrame} des données brutes chargées.
        """
        sources: dict[str, pd.DataFrame] = {}
        raw_files = {
            "tmdb": "raw_tmdb.json",
            "csv": "raw_csv.json",
            "mydramalist": "raw_scrape.json",
            "database": "raw_database.json",
        }

        for source_name, filename in raw_files.items():
            file_path = self.raw_dir / filename
            if not file_path.exists():
                logger.warning("Fichier brut introuvable: %s — source ignorée", file_path)
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                df = pd.DataFrame(data)
                sources[source_name] = df
                logger.info("Source '%s' chargée: %d enregistrements", source_name, len(df))
            except (json.JSONDecodeError, Exception) as e:
                logger.error("Erreur de chargement %s: %s", filename, e)

        return sources

    # -------------------------------------------------------------------
    # Étape 2 : Normalisation des schémas
    # -------------------------------------------------------------------

    def normalize_schema(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """Normalise un DataFrame vers le schéma commun du projet.

        Applique le mapping des noms de colonnes spécifiques à chaque
        source vers les noms normalisés du schéma commun.

        Args:
            df: DataFrame brut d'une source.
            source: Nom de la source ('tmdb', 'csv', 'mydramalist').

        Returns:
            DataFrame avec les colonnes normalisées.
        """
        # Mapping source -> schéma commun
        mappings = {
            "tmdb": {
                "tmdb_id": "tmdb_id",
                "titre": "titre",
                "english_name": "english_name",
                "titre_original": "titre_original",
                "date_diffusion": "date_diffusion",
                "nb_episodes": "nb_episodes",
                "nb_saisons": "nb_saisons",
                "synopsis": "synopsis",
                "note_moyenne": "note_moyenne",
                "nb_votes": "nb_votes",
                "langue_originale": "langue_originale",
                "pays_origine": "pays_origine",
                "genres": "genres",
                "reseaux_diffusion": "reseaux_diffusion",
                "acteurs": "acteurs",
            },
            "csv": {
                "titre": "titre",
                "english_name": "english_name",
                "date_diffusion": "date_diffusion",
                "annee_diffusion": "annee_diffusion",
                "reseaux_diffusion": "reseaux_diffusion",
                "nb_episodes": "nb_episodes",
                "duree_episode": "duree_episode",
                "genres": "genres",
                "note_moyenne": "note_moyenne",
                "acteurs": "acteurs",
                "synopsis": "synopsis",
                "tags": "tags",
                "rang": "rang",
                "popularite": "popularite",
            },
            "mydramalist": {
                "titre": "titre",
                "english_name": "english_name",
                "titre_original": "titre_original",
                "date_diffusion": "date_diffusion",
                "note_moyenne": "note_moyenne",
                "nb_votes": "nb_votes",
                "nb_watchers": "nb_watchers",
                "genres": "genres",
                "tags": "tags",
                "synopsis": "synopsis",
                "reseaux_diffusion": "reseaux_diffusion",
                "nb_episodes": "nb_episodes",
                "scenariste": "scenariste",
                "realisateur": "realisateur",
                "pays_origine": "pays_origine",
                "url": "url_source",
            },
            "database": {
                "titre": "titre",
                "english_name": "english_name",
                "titre_original": "titre_original",
                "date_diffusion": "date_diffusion",
                "nb_episodes": "nb_episodes",
                "synopsis": "synopsis",
                "note_moyenne": "note_moyenne",
                "nb_votes": "nb_votes",
                "langue_originale": "langue_originale",
                "pays_origine": "pays_origine",
                "genres": "genres",
                "reseaux_diffusion": "reseaux_diffusion",
            },
        }

        source_mapping = mappings.get(source, {})
        # Renommage des colonnes existantes
        cols_to_rename = {
            col: normalized
            for col, normalized in source_mapping.items()
            if col in df.columns
        }
        df = df.rename(columns=cols_to_rename)

        # Ajout de la colonne source
        df["source"] = source

        return df

    # -------------------------------------------------------------------
    # Étape 3 : Nettoyage des chaînes
    # -------------------------------------------------------------------

    def nettoyer_chaines(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoie les colonnes de type chaîne de caractères.

        Opérations effectuées :
            - Suppression des espaces de début et de fin.
            - Suppression des caractères de contrôle.
            - Normalisation Unicode (NFKD).
            - Suppression des balises HTML résiduelles.

        Args:
            df: DataFrame à nettoyer.

        Returns:
            DataFrame avec chaînes nettoyées.
        """
        colonnes_texte = df.select_dtypes(include=["object"]).columns

        for col in colonnes_texte:
            # On ne nettoie pas les colonnes de type liste (genres, acteurs, etc.)
            if col in ("genres", "acteurs", "tags", "reseaux_diffusion", "pays_origine"):
                continue

            df[col] = df[col].apply(self._nettoyer_chaine)

        return df

    @staticmethod
    def _nettoyer_chaine(valeur: Any) -> Any:
        """Nettoie une valeur chaîne individuelle.

        Args:
            valeur: Valeur à nettoyer (peut être None, str, ou autre type).

        Returns:
            Valeur nettoyée (str ou None si vide/NaN).
        """
        if pd.isna(valeur) or valeur is None:
            return None

        if not isinstance(valeur, str):
            return valeur

        # Suppression des balises HTML
        valeur = re.sub(r"<[^>]+>", "", valeur)
        # Normalisation Unicode NFKD (décomposition des caractères accentués)
        valeur = unicodedata.normalize("NFKD", valeur)
        # Suppression des caractères de contrôle (sauf tabulation et nouvelle ligne)
        valeur = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", valeur)
        # Suppression des espaces multiples
        valeur = re.sub(r"\s+", " ", valeur)
        # Trim
        valeur = valeur.strip()

        return valeur if valeur else None

    # -------------------------------------------------------------------
    # Étape 4 : Nettoyage des dates
    # -------------------------------------------------------------------

    def nettoyer_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalise la colonne date_diffusion au format ISO 8601.

        Gère plusieurs formats d'entrée :
            - ISO (2023-01-15)
            - Américain (01/15/2023 ou 01-15-2023)
            - Texte (Jan 15, 2023 ou January 15, 2023)
            - Année seule (2023 -> 2023-01-01)

        Args:
            df: DataFrame contenant la colonne date_diffusion.

        Returns:
            DataFrame avec dates au format ISO 8601 (YYYY-MM-DD).
        """
        if "date_diffusion" not in df.columns:
            return df

        def parse_date(valeur: Any) -> Any:
            if pd.isna(valeur) or valeur is None:
                return None

            if isinstance(valeur, (datetime, pd.Timestamp)):
                return valeur.strftime("%Y-%m-%d")

            valeur_str = str(valeur).strip()
            if not valeur_str:
                return None

            # Tentative de parsing multi-format
            try:
                dt = pd.to_datetime(valeur_str, format="mixed", errors="raise")
                return dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass

            # Tentative avec année seule (ex: "2023")
            if re.match(r"^\d{4}$", valeur_str):
                annee = int(valeur_str)
                if ANNEE_MIN <= annee <= ANNEE_MAX:
                    return f"{annee}-01-01"

            logger.debug("Date non parsable: %s", valeur_str)
            return None

        df["date_diffusion"] = df["date_diffusion"].apply(parse_date)

        # Nettoyage de la colonne annee_diffusion si présente
        if "annee_diffusion" in df.columns:
            df["annee_diffusion"] = pd.to_numeric(df["annee_diffusion"], errors="coerce")
            # Filtrage des années invalides
            df.loc[
                (df["annee_diffusion"] < ANNEE_MIN) | (df["annee_diffusion"] > ANNEE_MAX),
                "annee_diffusion",
            ] = None

        return df

    # -------------------------------------------------------------------
    # Étape 5 : Nettoyage des notes
    # -------------------------------------------------------------------

    def nettoyer_notes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoie et normalise la colonne note_moyenne sur l'échelle 0-10.

        Convertit les notes exprimées sous différents formats :
            - Float direct (8.5)
            - Chaîne avec barre (8.5/10)
            - Pourcentage (85%)
            - Note sur 100 (85)

        Args:
            df: DataFrame contenant la colonne note_moyenne.

        Returns:
            DataFrame avec notes normalisées (float, 0-10, 2 décimales).
        """
        if "note_moyenne" not in df.columns:
            return df

        def parse_note(valeur: Any) -> Optional[float]:
            if pd.isna(valeur) or valeur is None:
                return None

            # Si déjà numérique
            if isinstance(valeur, (int, float)):
                note = float(valeur)
            else:
                # Extraction du premier nombre de la chaîne
                match = re.search(r"(\d+\.?\d*)", str(valeur))
                if not match:
                    return None
                note = float(match.group(1))

            # Conversion si la note est sur 100
            if note > 10:
                note = note / 10

            # Validation de la plage
            if note < 0 or note > 10:
                logger.debug("Note hors plage: %s", note)
                return None

            return round(note, 2)

        df["note_moyenne"] = df["note_moyenne"].apply(parse_note)
        return df

    # -------------------------------------------------------------------
    # Étape 6 : Normalisation des genres
    # -------------------------------------------------------------------

    def normaliser_genres(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalise la liste des genres vers le référentiel commun.

        Applique le mapping GENRE_NORMALISATION pour convertir les genres
        depuis différentes conventions (anglais, variantes) vers un
        vocabulaire unifié en français.

        Args:
            df: DataFrame contenant la colonne genres (listes).

        Returns:
            DataFrame avec genres normalisés.
        """
        if "genres" not in df.columns:
            return df

        def normaliser_liste_genres(genres: Any) -> list[str]:
            if genres is None:
                return []
            if isinstance(genres, float) and pd.isna(genres):
                return []
            if isinstance(genres, str) and genres.strip() == "":
                return []

            # Si la valeur est une chaîne, la séparer
            if isinstance(genres, str):
                genres = re.split(r"[,|/;]", genres)
                genres = [g.strip() for g in genres if g.strip()]

            # Convertir un numpy array en liste
            if hasattr(genres, "tolist"):
                genres = genres.tolist()

            if not isinstance(genres, list):
                return []

            genres_normalises = []
            for genre in genres:
                if not genre or not isinstance(genre, str):
                    continue
                genre_key = unicodedata.normalize(
                    "NFKD", genre.strip().lower()
                ).encode("ascii", "ignore").decode("ascii")
                genre_normalise = GENRE_NORMALISATION.get(genre_key, genre.strip())
                if genre_normalise not in genres_normalises:
                    genres_normalises.append(genre_normalise)

            return genres_normalises

        df["genres"] = df["genres"].apply(normaliser_liste_genres)
        return df

    # -------------------------------------------------------------------
    # Étape 7 : Nettoyage des valeurs numériques
    # -------------------------------------------------------------------

    def nettoyer_numeriques(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convertit et valide les colonnes numériques.

        Colonnes traitées :
            - nb_episodes (int positif)
            - nb_saisons (int positif)
            - nb_votes (int positif)
            - duree_episode (int positif en minutes)

        Args:
            df: DataFrame à nettoyer.

        Returns:
            DataFrame avec valeurs numériques validées.
        """
        colonnes_int = ["nb_episodes", "nb_saisons", "nb_votes", "duree_episode"]

        for col in colonnes_int:
            if col not in df.columns:
                continue

            def parse_int(valeur: Any) -> Optional[int]:
                if pd.isna(valeur) or valeur is None:
                    return None
                if isinstance(valeur, (int, float)):
                    val = int(valeur)
                else:
                    match = re.search(r"(\d+)", str(valeur))
                    if not match:
                        return None
                    val = int(match.group(1))
                # Validation : doit être positif
                if val <= 0:
                    return None
                return val

            df[col] = df[col].apply(parse_int)

        return df

    # -------------------------------------------------------------------
    # Étape 8 : Suppression des entrées corrompues
    # -------------------------------------------------------------------

    def supprimer_corrompus(self, df: pd.DataFrame) -> pd.DataFrame:
        """Supprime les enregistrements corrompues ou invalides.

        Critères de suppression :
            - Titre manquant ou vide.
            - Date de diffusion avec année incohérente (< 1990 ou > 2025).
            - Note hors plage (< 0 ou > 10) — déjà géré par nettoyer_notes.
            - Nombre d'épisodes nul ou négatif.
            - Doublons exacts (toutes colonnes identiques).

        Args:
            df: DataFrame à filtrer.

        Returns:
            DataFrame sans les entrées corrompues.
        """
        nb_avant = len(df)

        # Titre obligatoire
        if "titre" in df.columns:
            df = df.dropna(subset=["titre"])
            df = df[df["titre"].str.strip() != ""]

        # Validation de l'année de diffusion
        if "date_diffusion" in df.columns:
            df["annee_temp"] = pd.to_datetime(df["date_diffusion"], errors="coerce").dt.year
            mask_annee_valide = df["annee_temp"].isna() | (
                (df["annee_temp"] >= ANNEE_MIN) & (df["annee_temp"] <= ANNEE_MAX)
            )
            df = df[mask_annee_valide]
            df = df.drop(columns=["annee_temp"])

        # Validation du nombre d'épisodes (si renseigné, doit être > 0)
        if "nb_episodes" in df.columns:
            df = df[df["nb_episodes"].isna() | (df["nb_episodes"] > 0)]

        # Suppression des doublons exacts
        # Les colonnes contenant des listes (ex: genres) ne sont pas hashables,
        # on les convertit temporairement en chaînes pour le dédoublonnage
        nb_avant_dedup = len(df)
        cols_liste = {}
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, list)).any():
                cols_liste[col] = df[col].copy()
                df[col] = df[col].apply(
                    lambda x: "|".join(str(i) for i in x) if isinstance(x, list) else x
                )
        df = df.drop_duplicates()
        for col, valeurs in cols_liste.items():
            df[col] = valeurs
        nb_doublons_exact = nb_avant_dedup - len(df)

        nb_apres = len(df)
        nb_supprimes = nb_avant - nb_apres
        logger.info(
            "Suppression des corrompus: %d supprimés (%d doublons exacts), reste %d",
            nb_supprimes,
            nb_doublons_exact,
            nb_apres,
        )

        return df

    # -------------------------------------------------------------------
    # Étape 9 : Fusion des sources
    # -------------------------------------------------------------------

    def fusionner_sources(self, dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Fusionne les DataFrames des différentes sources en un seul.

        Stratégie de fusion :
            1. Concaténation de tous les DataFrames.
            2. Génération d'une clé de correspondance (titre normalisé).
            3. Détection des doublons par similarité de titre (Levenshtein/SequenceMatcher).
            4. Fusion des doublons en conservant les valeurs non-nulles par priorité :
               TMDB > MyDramaList > CSV.

        Args:
            dfs: Dictionnaire {source: DataFrame} des données nettoyées.

        Returns:
            DataFrame fusionné et dédoublonné.
        """
        if not dfs:
            return pd.DataFrame()

        # Concaténation de toutes les sources
        df_all = pd.concat(dfs.values(), ignore_index=True)
        logger.info("Concaténation: %d enregistrements au total", len(df_all))

        # Génération de la clé de correspondance (titre normalisé)
        df_all["titre_normalise"] = df_all["titre"].apply(self._normaliser_titre)

        # Tri par priorité de source (TMDB > MyDramaList > CSV)
        priorite_source = {"tmdb": 1, "mydramalist": 2, "csv": 3, "database": 4}
        df_all["priorite_source"] = df_all["source"].map(
            lambda s: priorite_source.get(s, 99)
        )
        df_all = df_all.sort_values("priorite_source")

        # Détection et fusion des doublons par similarité de titre
        df_fusionne = self._dedupliquer_par_similarite(df_all)

        # Suppression des colonnes temporaires
        df_fusionne = df_fusionne.drop(columns=["titre_normalise", "priorite_source"], errors="ignore")

        logger.info("Fusion terminée: %d enregistrements uniques", len(df_fusionne))
        return df_fusionne

    @staticmethod
    def _normaliser_titre(titre: Any) -> str:
        """Normalise un titre pour la comparaison de doublons.

        Opérations : lowercase, suppression des accents, suppression
        de la ponctuation et des espaces superflus.

        Args:
            titre: Titre à normaliser.

        Returns:
            Titre normalisé (clé de correspondance).
        """
        if pd.isna(titre) or titre is None:
            return ""

        titre_str = str(titre).lower().strip()
        # Suppression des accents (NFKD + filtre des combining marks)
        titre_str = unicodedata.normalize("NFKD", titre_str)
        titre_str = "".join(c for c in titre_str if not unicodedata.combining(c))
        # Suppression de la ponctuation et caractères spéciaux
        titre_str = re.sub(r"[^\w\s]", "", titre_str)
        # Suppression des espaces multiples
        titre_str = re.sub(r"\s+", " ", titre_str).strip()

        return titre_str

    def _dedupliquer_par_similarite(self, df: pd.DataFrame) -> pd.DataFrame:
        """Détecte et fusionne les doublons par similarité de titre.

        Utilise difflib.SequenceMatcher pour comparer les titres normalisés.
        Deux enregistrements sont considérés comme doublons si le ratio de
        similarité dépasse SEUIL_SIMILARITE_TITRE (0.90 par défaut).

        Args:
            df: DataFrame trié par priorité de source.

        Returns:
            DataFrame dédoublonné avec fusion des champs non-nulles.
        """
        titres = df["titre_normalise"].tolist()
        indices_a_fusionner: list[tuple[int, int]] = []
        deja_vu: set[int] = set()

        # Comparaison par paires (O(n²) — acceptable pour quelques milliers d'enregistrements)
        for i in range(len(titres)):
            if i in deja_vu or not titres[i]:
                continue
            for j in range(i + 1, len(titres)):
                if j in deja_vu or not titres[j]:
                    continue
                ratio = SequenceMatcher(None, titres[i], titres[j]).ratio()
                if ratio >= SEUIL_SIMILARITE_TITRE:
                    indices_a_fusionner.append((i, j))
                    deja_vu.add(j)

        # Fusion des doublons : on garde l'enregistrement de plus haute priorité (i)
        # et on complète ses champs manquants avec ceux de j
        df_reset = df.reset_index(drop=True)
        lignes_a_supprimer: set[int] = set()

        for i, j in indices_a_fusionner:
            if i in lignes_a_supprimer:
                continue
            # Compléter les champs manquants de i avec ceux de j
            for col in df_reset.columns:
                if col in ("titre_normalise", "priorite_source", "source", "url_source"):
                    continue
                val_i = df_reset.at[i, col]
                val_j = df_reset.at[j, col]
                # pd.isna peut renvoyer un tableau pour les cellules de type
                # liste/dict — on se ramène à un booléen scalaire.
                i_manquant = (
                    len(val_i) == 0
                    if isinstance(val_i, (list, dict))
                    else bool(pd.isna(val_i))
                )
                j_present = (
                    len(val_j) > 0
                    if isinstance(val_j, (list, dict))
                    else not bool(pd.isna(val_j))
                )
                if i_manquant and j_present:
                    df_reset.at[i, col] = val_j
            lignes_a_supprimer.add(j)

        df_final = df_reset.drop(index=list(lignes_a_supprimer)).reset_index(drop=True)
        logger.info(
            "Dédoublonnage par similarité: %d doublons fusionnés, reste %d",
            len(lignes_a_supprimer),
            len(df_final),
        )
        return df_final

    # -------------------------------------------------------------------
    # Étape 10 : Calcul du rapport de qualité
    # -------------------------------------------------------------------

    def calculer_rapport_qualite(
        self,
        dfs_bruts: dict[str, pd.DataFrame],
        df_final: pd.DataFrame,
        nb_doublons: int,
    ) -> QualityReport:
        """Calcule un rapport de qualité des données traitées.

        Args:
            dfs_bruts: DataFrames bruts par source.
            df_final: DataFrame final après nettoyage et fusion.
            nb_doublons: Nombre de doublons supprimés.

        Returns:
            Objet QualityReport avec les statistiques.
        """
        rapport = QualityReport()
        rapport.total_brut = sum(len(df) for df in dfs_bruts.values())
        rapport.total_apres_fusion = len(df_final)
        rapport.doublons_supprimes = nb_doublons
        rapport.total_apres_nettoyage = rapport.total_brut  # Ajusté après nettoyage

        for source, df in dfs_bruts.items():
            rapport.par_source[source] = len(df)

        # Calcul des valeurs manquantes et taux de complétude
        for col in df_final.columns:
            if col in ("titre_normalise", "priorite_source"):
                continue
            nb_manquants = int(df_final[col].isna().sum())
            rapport.valeurs_manquantes[col] = nb_manquants
            if len(df_final) > 0:
                taux = ((len(df_final) - nb_manquants) / len(df_final)) * 100
                rapport.taux_completude[col] = round(taux, 1)

        return rapport

    # -------------------------------------------------------------------
    # Étape 11 : Export des données
    # -------------------------------------------------------------------

    def export_json(self, df: pd.DataFrame, filename: str = "kdramas_clean.json") -> Path:
        """Exporte le DataFrame nettoyé au format JSON.

        Args:
            df: DataFrame à exporter.
            filename: Nom du fichier de sortie.

        Returns:
            Chemin du fichier créé.
        """
        file_path = self.clean_dir / filename
        # Conversion des colonnes de type liste en listes JSON sérialisables
        records = df.to_dict(orient="records")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Export JSON: %s (%d enregistrements)", file_path, len(df))
        return file_path

    def export_csv(self, df: pd.DataFrame, filename: str = "kdramas_clean.csv") -> Path:
        """Exporte le DataFrame nettoyé au format CSV.

        Args:
            df: DataFrame à exporter.
            filename: Nom du fichier de sortie.

        Returns:
            Chemin du fichier créé.
        """
        file_path = self.clean_dir / filename
        df.to_csv(file_path, index=False, encoding="utf-8")
        logger.info("Export CSV: %s (%d enregistrements)", file_path, len(df))
        return file_path

    def export_database(self, df: pd.DataFrame) -> None:
        """Exporte le DataFrame nettoyé vers la base PostgreSQL.

        Insère les données dans la table kdramas via SQLAlchemy.
        Les colonnes de type liste sont converties en tableaux PostgreSQL.

        Args:
            df: DataFrame à exporter.
        """
        if self.engine is None:
            logger.warning("Pas de base de données configurée — export DB ignoré")
            return

        # Préparation du DataFrame pour l'insertion
        df_export = df.copy()
        # Conversion des listes en chaînes séparées par virgule pour l'insertion
        for col in ("genres", "acteurs", "tags", "reseaux_diffusion", "pays_origine"):
            if col in df_export.columns:
                df_export[col] = df_export[col].apply(
                    lambda x: json.dumps(x, ensure_ascii=False, default=str)
                    if isinstance(x, (list, dict)) else x
                )

        try:
            df_export.to_sql("kdramas", self.engine, if_exists="append", index=False)
            logger.info("Export base de données: %d enregistrements insérés", len(df_export))
        except Exception as e:
            logger.error("Erreur d'export en base: %s", e)

    # -------------------------------------------------------------------
    # Pipeline complet
    # -------------------------------------------------------------------

    def run_pipeline(self) -> tuple[pd.DataFrame, QualityReport]:
        """Exécute le pipeline complet d'agrégation et de nettoyage.

        Étapes :
            1. Chargement des données brutes.
            2. Normalisation des schémas par source.
            3. Nettoyage des chaînes, dates, notes, genres, numériques.
            4. Suppression des entrées corrompues.
            5. Fusion des sources par similarité de titre.
            6. Calcul du rapport de qualité.
            7. Export JSON, CSV et base de données.

        Returns:
            Tuple (DataFrame final, QualityReport).
        """
        logger.info("=" * 60)
        logger.info("DÉMARRAGE DU PIPELINE D'AGRÉGATION")
        logger.info("=" * 60)
        start_time = datetime.now()

        # Étape 1 : chargement
        sources_brutes = self.load_raw_data()
        if not sources_brutes:
            logger.error("Aucune source de données trouvée — arrêt du pipeline")
            return pd.DataFrame(), QualityReport()

        # Étape 2 : normalisation des schémas
        sources_normalisees: dict[str, pd.DataFrame] = {}
        for source_name, df in sources_brutes.items():
            df_norm = self.normalize_schema(df, source_name)
            sources_normalisees[source_name] = df_norm

        # Étapes 3-7 : nettoyage pour chaque source
        sources_nettoyees: dict[str, pd.DataFrame] = {}
        for source_name, df in sources_normalisees.items():
            logger.info("--- Nettoyage source: %s ---", source_name)
            df = self.nettoyer_chaines(df)
            df = self.nettoyer_dates(df)
            df = self.nettoyer_notes(df)
            df = self.normaliser_genres(df)
            df = self.nettoyer_numeriques(df)
            df = self.supprimer_corrompus(df)
            sources_nettoyees[source_name] = df

        # Étape 8 : fusion
        nb_avant_fusion = sum(len(df) for df in sources_nettoyees.values())
        df_fusionne = self.fusionner_sources(sources_nettoyees)
        nb_doublons = nb_avant_fusion - len(df_fusionne)

        # Étape 9 : rapport de qualité
        rapport = self.calculer_rapport_qualite(sources_brutes, df_fusionne, nb_doublons)
        rapport.total_apres_nettoyage = nb_avant_fusion
        rapport.afficher()

        # Étape 10 : exports
        self.export_json(df_fusionne)
        self.export_csv(df_fusionne)
        self.export_database(df_fusionne)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("Pipeline terminé en %.1fs — %d enregistrements finaux", elapsed, len(df_fusionne))
        logger.info("=" * 60)

        return df_fusionne, rapport


# ===========================================================================
# Point d'entrée du script
# ===========================================================================
if __name__ == "__main__":
    aggregator = DataAggregator()
    df_final, rapport = aggregator.run_pipeline()
    print(f"\nPipeline terminé: {len(df_final)} K-Dramas après nettoyage et fusion.")
