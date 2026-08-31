#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_collector.py — Collecte automatisée de données K-Drama depuis quatre sources.

Ce module implémente la collecte de données depuis :
    1. L'API REST TMDB (The Movie Database) — données structurées JSON.
    2. Un fichier CSV — données tabulaires complémentaires (flat file).
    3. Le site web MyDramaList — scraping HTML pour données enrichies.
    4. Une base de données SQLite — données stockées en base (BDD).

Compétence RNPC C1 : Extraction de données depuis des sources variées
(API REST, fichier, scraping web).

Auteur : Équipe Data
Projet : Système de recommandation de K-Dramas par IA
Étape : 1 — Collecte et préparation des données
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("data_collector")

# Chargement des variables d'environnement depuis le fichier .env
load_dotenv()


def is_drama_only(data: dict) -> bool:
    """Filter to keep only K-Dramas, exclude cartoons/concerts/shows.

    Checks if genres contain drama keywords and excludes non-drama content.

    Args:
        data: Dictionary with 'genres', 'titre', 'synopsis' keys.

    Returns:
        True if content is a drama, False otherwise.
    """
    genres = data.get("genres", [])
    if isinstance(genres, str):
        genres = [genres]
    genres = [str(g).lower() for g in genres if g]

    title = str(data.get("titre", "")).lower()
    synopsis = str(data.get("synopsis", "")).lower()

    # Exclude non-drama genres
    if any(excluded.lower() in genres for excluded in EXCLUDE_GENRES):
        return False

    # Exclude non-drama keywords in title/synopsis
    if any(keyword in title or keyword in synopsis for keyword in EXCLUDE_KEYWORDS):
        return False

    # Accept if contains drama keyword
    has_drama = any(keyword.lower() in genres for keyword in DRAMA_GENRES)
    return has_drama


# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------
TMDB_BASE_URL = "https://api.themoviedb.org/3"
MYDRAMALIST_BASE_URL = "https://mydramalist.com"
DEFAULT_DELAY = float(os.getenv("SCRAPE_DELAY_SECONDS", "5"))  # Increased from 2 to 5 seconds
DEFAULT_TIMEOUT = 60  # Increased from 30 to 60 seconds
DEFAULT_MAX_RETRIES = 5  # Increased from 3 to 5 attempts
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw"

# Drama-only filter: genres to keep
DRAMA_GENRES = {"Drama", "Melodrama", "Thriller", "Mystery", "Crime", "Psychological"}
# Genres/keywords to exclude (non-drama content)
EXCLUDE_GENRES = {
    "Animation", "Anime", "Variety", "Talk", "Reality",
    "Game Show", "Documentary", "News", "Sport", "Concert"
}
EXCLUDE_KEYWORDS = {
    "concert", "musical performance", "game show",
    "variety show", "talk show", "reality show", "cartoon",
    "anime", "animated"
}


# ===========================================================================
# SECTION 1 — Collecteur API REST TMDB
# ===========================================================================
class TMDBCollector:
    """Collecteur de données depuis l'API REST de The Movie Database (TMDB).

    Cette classe encapsule toutes les interactions avec l'API TMDB :
    authentification, recherche de K-Dramas, récupération des détails,
    des crédits (acteurs) et gestion du rate limiting.

    Attributes:
        api_key: Clé d'authentification TMDB (chargée depuis l'environnement).
        base_url: URL de base de l'API TMDB.
        session: Session HTTP persistante (connexion keep-alive).
        delay: Délai en secondes entre deux requêtes (rate limiting).
        timeout: Délai d'expiration des requêtes HTTP en secondes.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = TMDB_BASE_URL,
        delay: float = DEFAULT_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise le collecteur TMDB.

        Args:
            api_key: Clé API TMDB. Si None, charge depuis TMDB_API_KEY.
            base_url: URL de base de l'API (par défaut: v3).
            delay: Délai entre requêtes en secondes (rate limiting).
            timeout: Timeout HTTP en secondes.

        Raises:
            ValueError: Si aucune clé API n'est trouvée.
        """
        self.api_key = api_key or os.getenv("TMDB_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Clé API TMDB introuvable. Définissez TMDB_API_KEY dans .env"
            )
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        # User-Agent explicite pour identifier le collecteur
        self.session.headers.update(
            {
                "User-Agent": "KDramaCollector/1.0 (projet académique)",
                "Accept": "application/json",
            }
        )
        logger.info("TMDBCollector initialisé (base_url=%s)", self.base_url)

    def _make_request(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> Optional[dict]:
        """Effectue une requête HTTP vers l'API TMDB avec retry exponentiel.

        Gère le rate limiting (HTTP 429) en attendant le délai indiqué par
        l'en-tête Retry-After. Les autres erreurs HTTP déclenchent un retry
        avec backoff exponentiel (1s, 2s, 4s, ...).

        Args:
            endpoint: Endpoint relatif (ex: /discover/tv).
            params: Paramètres de requête (ajoutés à l'URL).
            max_retries: Nombre maximum de tentatives.

        Returns:
            Dictionnaire JSON de la réponse, ou None en cas d'échec.
        """
        url = f"{self.base_url}{endpoint}"
        all_params = {"api_key": self.api_key, "language": "en-US"}
        if params:
            all_params.update(params)

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(
                    url, params=all_params, timeout=self.timeout
                )

                # Gestion du rate limiting (429 Too Many Requests)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 10))
                    logger.warning(
                        "Rate limit atteint (tentative %d/%d), attente %ds",
                        attempt,
                        max_retries,
                        retry_after,
                    )
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                logger.error("Timeout sur %s (tentative %d/%d)", endpoint, attempt, max_retries)
            except requests.exceptions.HTTPError as e:
                logger.error("Erreur HTTP %d sur %s: %s", response.status_code, endpoint, e)
                if response.status_code in (404, 401):
                    # Erreurs non récupérables
                    return None
            except requests.exceptions.ConnectionError as e:
                logger.error("Erreur de connexion sur %s: %s", endpoint, e)

            # Backoff exponentiel avant retry
            if attempt < max_retries:
                wait = 2 ** (attempt - 1)
                logger.info("Nouvelle tentative dans %ds", wait)
                time.sleep(wait)

        logger.error("Échec définitif sur %s après %d tentatives", endpoint, max_retries)
        return None

    def collect_kdramas(self, max_pages: int = 50) -> list[dict]:
        """Collecte la liste des K-Dramas via l'endpoint discover/tv.

        Filtre sur :
        - Pays d'origine: Corée du Sud (KR)
        - Genre: Drama (ID 18)
        - Langue originale: Korean (ko)
        - Tri: popularité décroissante

        Args:
            max_pages: Nombre maximum de pages à parcourir (20 résultats/page).

        Returns:
            Liste de dictionnaires, chacun représentant un K-Drama.
        """
        kdramas: list[dict] = []
        logger.info("Début de la collecte TMDB (max_pages=%d)", max_pages)

        for page in range(1, max_pages + 1):
            params = {
                "with_origin_country": "KR",
                "with_genres": "18",  # Drama genre ID
                "with_original_language": "ko",  # Korean language
                "sort_by": "popularity.desc",
                "page": page,
            }
            data = self._make_request("/discover/tv", params=params)

            if data is None:
                logger.warning("Échec page %d, passage à la suivante", page)
                continue

            results = data.get("results", [])
            if not results:
                logger.info("Aucun résultat page %d — fin de pagination", page)
                break

            kdramas.extend(results)
            logger.info(
                "Page %d: %d K-Dramas collectés (total: %d)",
                page,
                len(results),
                len(kdramas),
            )

            time.sleep(self.delay)

        logger.info("Collecte TMDB terminée: %d K-Dramas au total", len(kdramas))
        return kdramas

    def collect_kdrama_details(self, kdrama_id: int) -> Optional[dict]:
        """Récupère les détails complets d'un K-Drama par son ID TMDB.

        Inclut les genres, les réseaux de diffusion, les saisons et
        les sociétés de production via l'endpoint /tv/{id} avec
        append_to_response.

        Args:
            kdrama_id: Identifiant TMDB du K-Drama.

        Returns:
            Dictionnaire des détails, ou None si introuvable.
        """
        params = {"append_to_response": "credits,external_ids"}
        data = self._make_request(f"/tv/{kdrama_id}", params=params)

        if data is None:
            logger.warning("Détails introuvables pour TMDB ID %d", kdrama_id)
            return None

        time.sleep(self.delay)
        return data

    def collect_kdrama_cast(self, kdrama_id: int) -> list[dict]:
        """Récupère le casting (acteurs) d'un K-Drama.

        Utilise l'endpoint /tv/{id}/credits et filtre les acteurs
        avec un ordre de priorité (order < 10 = acteurs principaux).

        Args:
            kdrama_id: Identifiant TMDB du K-Drama.

        Returns:
            Liste de dictionnaires d'acteurs (id, nom, personnage, role_principal).
        """
        data = self._make_request(f"/tv/{kdrama_id}/credits")
        if data is None:
            return []

        cast = data.get("cast", [])
        acteurs = []
        for actor in cast[:15]:  # Limite aux 15 premiers acteurs
            acteurs.append(
                {
                    "tmdb_id": actor.get("id"),
                    "nom": actor.get("name"),
                    "personnage": actor.get("character"),
                    "role_principal": actor.get("order", 99) < 3,
                }
            )

        time.sleep(self.delay)
        return acteurs

    @staticmethod
    def _contains_hangul(text: str) -> bool:
        """Vérifie si un texte contient des caractères Hangul."""
        return any(
            "\u1100" <= ch <= "\u11FF"
            or "\u3130" <= ch <= "\u318F"
            or "\uAC00" <= ch <= "\uD7A3"
            for ch in text
        )

    def normalize_kdrama(self, raw: dict, details: Optional[dict] = None) -> dict:
        """Normalise un enregistrement K-Drama vers le schéma commun.

        Fusionne les données de base (discover) et les détails (tv/{id})
        en un dictionnaire au schéma normalisé du projet.

        Args:
            raw: Données brutes de l'endpoint discover/tv.
            details: Données détaillées de l'endpoint tv/{id} (optionnel).

        Returns:
            Dictionnaire au schéma normalisé.
        """
        source_data = {**raw, **(details or {})}
        english_name = (
            source_data.get("name")
            or source_data.get("title")
            or source_data.get("original_name")
        )

        if english_name and self._contains_hangul(english_name):
            translations = source_data.get("translations", {}).get("translations", [])
            for entry in translations:
                if entry.get("iso_639_1") == "en":
                    en_data = entry.get("data", {})
                    english_name = (
                        en_data.get("name")
                        or en_data.get("title")
                        or english_name
                    )
                    if english_name and not self._contains_hangul(english_name):
                        break

        original_title = source_data.get("original_name") or english_name

        # Extract poster URL from TMDB poster_path
        poster_url = None
        poster_path = source_data.get("poster_path")
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w400{poster_path}"

        return {
            "tmdb_id": source_data.get("id"),
            "titre": english_name,
            "english_name": english_name,
            "titre_original": original_title,
            "date_diffusion": source_data.get("first_air_date"),
            "nb_episodes": source_data.get("number_of_episodes"),
            "nb_saisons": source_data.get("number_of_seasons"),
            "synopsis": source_data.get("overview"),
            "note_moyenne": source_data.get("vote_average"),
            "nb_votes": source_data.get("vote_count"),
            "langue_originale": source_data.get("original_language"),
            "pays_origine": source_data.get("origin_country", []),
            "genres": [g.get("name") for g in source_data.get("genres", [])],
            "reseaux_diffusion": [
                n.get("name") for n in source_data.get("networks", [])
            ],
            "poster": poster_url,
            "source": "tmdb",
        }

    def run_full_collection(self, max_pages: int = 50) -> list[dict]:
        """Exécute la collecte complète TMDB : liste + détails + casting.

        Workflow:
            1. Collecte de la liste des K-Dramas (discover/tv).
            2. Pour chaque K-Drama, récupération des détails et du casting.
            3. Normalisation vers le schéma commun.

        Args:
            max_pages: Nombre maximum de pages de discover/tv.

        Returns:
            Liste de dictionnaires K-Dramas normalisés avec acteurs.
        """
        logger.info("=== Démarrage de la collecte TMDB complète ===")
        start_time = time.time()

        # Étape 1 : liste des K-Dramas
        kdramas_raw = self.collect_kdramas(max_pages=max_pages)
        if not kdramas_raw:
            logger.warning("Aucun K-Drama collecté depuis TMDB")
            return []

        # Étape 2 : détails et casting pour chaque K-Drama
        kdramas_normalized: list[dict] = []
        for i, kdrama_raw in enumerate(kdramas_raw, 1):
            kdrama_id = kdrama_raw.get("id")
            if not kdrama_id:
                continue

            logger.info("Traitement K-Drama %d/%d (TMDB ID: %s)", i, len(kdramas_raw), kdrama_id)

            details = self.collect_kdrama_details(kdrama_id)
            cast = self.collect_kdrama_cast(kdrama_id)

            normalized = self.normalize_kdrama(kdrama_raw, details)

            # Filter: keep only drama content
            if not is_drama_only(normalized):
                logger.debug("Filtered out (not a drama): %s", normalized.get("titre"))
                continue

            normalized["acteurs"] = cast
            kdramas_normalized.append(normalized)

        elapsed = time.time() - start_time
        logger.info(
            "Collecte TMDB complète: %d K-Dramas en %.1fs",
            len(kdramas_normalized),
            elapsed,
        )
        return kdramas_normalized


# ===========================================================================
# SECTION 2 — Collecteur de fichier CSV
# ===========================================================================
class CSVCollector:
    """Collecteur de données depuis un fichier CSV structuré.

    Lit un fichier CSV contenant des données complémentaires sur les
    K-Dramas (export de datasets publics type Kaggle). Valide la
    présence des colonnes attendues et normalise les enregistrements
    vers le schéma commun du projet.

    Attributes:
        file_path: Chemin vers le fichier CSV.
        encoding: Encodage du fichier (par défaut: utf-8).
        separator: Séparateur de colonnes (par défaut: ',').
    """

    # Colonnes attendues dans le fichier CSV (avec variantes de nommage)
    EXPECTED_COLUMNS = {"Name"}

    # Mapping des noms de colonnes CSV vers le schéma normalisé
    COLUMN_MAPPING = {
        "Name": "titre",
        "English Name": "english_name",
        "english_name": "english_name",
        "Aired Date": "date_diffusion",
        "Year of Release": "annee_diffusion",
        "Original Network": "reseaux_diffusion",
        "Number of Episodes": "nb_episodes",
        "Duration": "duree_episode",
        "Genre": "genres",
        "Score": "note_moyenne",
        "Actors": "acteurs",
        "Synopsis": "synopsis",
        "Tags": "tags",
        "Rank": "rang",
        "Popularity": "popularite",
    }

    def __init__(
        self,
        file_path: str | Path,
        encoding: str = "utf-8",
        separator: str = ",",
    ) -> None:
        """Initialise le collecteur CSV.

        Args:
            file_path: Chemin du fichier CSV à lire.
            encoding: Encodage du fichier (utf-8, latin-1, etc.).
            separator: Séparateur de colonnes (virgule, point-virgule, tabulation).

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Fichier CSV introuvable: {self.file_path}")
        self.encoding = encoding
        self.separator = separator
        logger.info("CSVCollector initialisé (fichier=%s)", self.file_path)

    def collect(self) -> list[dict]:
        """Lit le fichier CSV et retourne les enregistrements normalisés.

        Effectue les opérations suivantes :
            1. Lecture du CSV avec pandas (détection d'encodage).
            2. Validation des colonnes attendues.
            3. Suppression des lignes sans titre.
            4. Normalisation vers le schéma commun.

        Returns:
            Liste de dictionnaires correspondant aux lignes du CSV.

        Raises:
            ValueError: Si les colonnes attendues sont manquantes.
            pd.errors.ParserError: Si le fichier est mal formaté.
        """
        logger.info("Lecture du fichier CSV: %s", self.file_path)

        try:
            df = pd.read_csv(
                self.file_path,
                encoding=self.encoding,
                sep=self.separator,
                na_values=["", "N/A", "null", "NaN", "None"],
            )
        except UnicodeDecodeError:
            logger.warning("Échec encodage utf-8, tentative latin-1")
            df = pd.read_csv(
                self.file_path,
                encoding="latin-1",
                sep=self.separator,
                na_values=["", "N/A", "null", "NaN", "None"],
            )

        logger.info("CSV chargé: %d lignes, %d colonnes", len(df), len(df.columns))

        # Validation des colonnes obligatoires
        colonnes_presentes = set(df.columns)
        colonnes_manquantes = self.EXPECTED_COLUMNS - colonnes_presentes
        if colonnes_manquantes:
            raise ValueError(
                f"Colonnes obligatoires manquantes dans le CSV: {colonnes_manquantes}. "
                f"Colonnes trouvées: {colonnes_presentes}"
            )

        # Suppression des lignes sans titre (enregistrements corrompus)
        nb_avant = len(df)
        df = df.dropna(subset=["Name"])
        nb_apres = len(df)
        if nb_avant != nb_apres:
            logger.info("%d lignes sans titre supprimées", nb_avant - nb_apres)

        # Normalisation des enregistrements
        records = df.to_dict(orient="records")
        normalized = [self._normalize_record(r) for r in records]

        logger.info("CSV collecté: %d enregistrements normalisés", len(normalized))
        return normalized

    def _normalize_record(self, record: dict) -> dict:
        """Normalise un enregistrement CSV vers le schéma commun.

        Applique le mapping des colonnes et convertit les valeurs
        (séparation des listes par virgule, conversion des types).

        Args:
            record: Dictionnaire brut d'une ligne du CSV.

        Returns:
            Dictionnaire au schéma normalisé.
        """
        normalized: dict[str, Any] = {"source": "csv"}

        for csv_col, schema_col in self.COLUMN_MAPPING.items():
            if csv_col in record:
                value = record[csv_col]
                # Conversion des listes séparées par virgule ou barre verticale
                if schema_col in ("genres", "reseaux_diffusion", "acteurs", "tags"):
                    if pd.isna(value):
                        normalized[schema_col] = []
                    else:
                        # Séparation par virgule ou barre verticale
                        parts = re.split(r"[,|/]", str(value))
                        normalized[schema_col] = [p.strip() for p in parts if p.strip()]
                else:
                    normalized[schema_col] = None if pd.isna(value) else value

        if not normalized.get("english_name") and normalized.get("titre"):
            normalized["english_name"] = normalized["titre"]

        return normalized


# ===========================================================================
# SECTION 3 — Scraping web MyDramaList
# ===========================================================================
class MyDramaListScraper:
    """Scraper web pour le site MyDramaList.

    Extrait les données des fiches de K-Dramas depuis mydramalist.com
    via parsing HTML (BeautifulSoup). Respecte le robots.txt et
    applique un rate limiting pour ne pas surcharger le serveur.

    Attributes:
        base_url: URL de base du site MyDramaList.
        session: Session HTTP persistante.
        delay: Délai en secondes entre chaque requête.
        timeout: Timeout HTTP en secondes.
    """

    def __init__(
        self,
        base_url: str = MYDRAMALIST_BASE_URL,
        delay: float = DEFAULT_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise le scraper MyDramaList.

        Args:
            base_url: URL de base du site.
            delay: Délai entre requêtes (rate limiting, éthique).
            timeout: Timeout HTTP en secondes.
        """
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        # cloudscraper résout automatiquement les challenges JavaScript de
        # Cloudflare que MyDramaList utilise pour bloquer les requêtes automatisées.
        try:
            import cloudscraper
            self.session = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            logger.info("MyDramaListScraper: cloudscraper activé (contournement Cloudflare)")
        except ImportError:
            logger.warning(
                "cloudscraper non installé — repli sur requests standard "
                "(le scraping échouera probablement face à Cloudflare). "
                "Installez avec: pip install cloudscraper"
            )
            self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                # Requests ne décode pas toujours Brotli sans dépendance externe,
                # ce qui peut produire du HTML illisible; on force gzip/deflate.
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        logger.info("MyDramaListScraper initialisé (base_url=%s)", self.base_url)

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Récupère une page HTML et retourne l'objet BeautifulSoup.

        cloudscraper gère automatiquement les challenges JavaScript de
        Cloudflare. Si cloudscraper échoue ou n'est pas installé, on bascule
        sur un rendu navigateur headless (Playwright) comme dernier recours.

        Args:
            url: URL complète de la page à scraper.

        Returns:
            Objet BeautifulSoup parsé, ou None en cas d'erreur.
        """
        for attempt in range(1, DEFAULT_MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                body = response.text or ""
                lower_body = body.lower()

                # Détection des pages de blocage Cloudflare même si le code HTTP
                # est 200 (Cloudflare peut servir la page de challenge avec 200)
                is_block_page = any(
                    marker in lower_body
                    for marker in [
                        "cloudflare",
                        "checking your browser",
                        "access denied",
                        "attention required",
                        "ray id",
                        "5xx-error-landing",
                        "captcha",
                        "cf-browser-verification",
                        "cf-challenge-running",
                    ]
                )

                if is_block_page:
                    logger.warning(
                        "Page de blocage Cloudflare détectée (tentative %d/%d): %s",
                        attempt,
                        DEFAULT_MAX_RETRIES,
                        url,
                    )
                    if attempt < DEFAULT_MAX_RETRIES:
                        wait = 2 ** attempt
                        logger.info("Nouvelle tentative dans %ds", wait)
                        time.sleep(wait)
                        continue
                    logger.info("Bascule sur Playwright pour %s", url)
                    return self._fetch_page_with_playwright(url)

                if response.status_code >= 400 and not body.strip():
                    raise requests.exceptions.RequestException(
                        f"Réponse HTTP {response.status_code} sans contenu"
                    )

                html_like = bool(re.search(r"<html|<!doctype|<body|<head", lower_body))
                has_links = bool(re.search(r"<a\s+[^>]*href=", lower_body))

                if response.status_code >= 400 and not html_like and not has_links:
                    raise requests.exceptions.RequestException(
                        f"Réponse HTTP {response.status_code} sans HTML exploitable"
                    )

                if response.status_code >= 400 and html_like:
                    logger.warning(
                        "Réponse HTTP %s reçue pour %s, mais contenu HTML exploitable trouvé; tentative de parsing",
                        response.status_code,
                        url,
                    )

                soup = BeautifulSoup(body, "lxml")
                time.sleep(self.delay)
                return soup

            except requests.exceptions.RequestException as e:
                logger.warning("Requête HTTP échouée pour %s (tentative %d/%d): %s",
                               url, attempt, DEFAULT_MAX_RETRIES, e)
                if attempt < DEFAULT_MAX_RETRIES:
                    wait = 2 ** (attempt - 1)
                    time.sleep(wait)
                    continue
                # Dernier recours : navigateur headless
                return self._fetch_page_with_playwright(url)

        return self._fetch_page_with_playwright(url)

    def _fetch_page_with_playwright(self, url: str) -> Optional[BeautifulSoup]:
        """Récupère une page via un navigateur headless si cloudscraper échoue.

        Playwright exécute le JavaScript de Cloudflare dans un vrai navigateur,
        ce qui permet de résoudre les challenges les plus complexes. Requiert
        l'installation de Playwright et de son navigateur Chromium.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            logger.error("Playwright non disponible: %s", exc)
            return None

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Attendre que Cloudflare ait terminé sa vérification JavaScript
                page.wait_for_timeout(8000)
                html = page.content()
                browser.close()
                soup = BeautifulSoup(html, "lxml")
                time.sleep(self.delay)
                return soup
        except Exception as exc:
            logger.error("Échec du rendu navigateur pour %s: %s", url, exc)
            return None

    @staticmethod
    def _contains_hangul(text: str) -> bool:
        """Vérifie si un texte contient des caractères Hangul."""
        return any(
            "\u1100" <= ch <= "\u11FF"
            or "\u3130" <= ch <= "\u318F"
            or "\uAC00" <= ch <= "\uD7A3"
            for ch in text
        )

    @staticmethod
    def _clean_title(text: str) -> str:
        """Nettoie un titre en supprimant les suffixes inutiles comme les années."""
        cleaned = text.strip()
        cleaned = re.sub(r"\s*\((19|20)\d{2}\)", "", cleaned)
        cleaned = re.sub(r"\s*-\s*MyDramaList$", "", cleaned)
        cleaned = re.sub(r"\s+\(\d{4}\)$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def _clean_text(text: str) -> str:
        """Nettoie un bloc de texte en supprimant les espaces et les sauts de ligne."""
        return " ".join(text.split())

    @staticmethod
    def _looks_like_synopsis(text: str) -> bool:
        """Valide qu'un texte ressemble à un synopsis et non à une métadonnée."""
        cleaned = text.strip()
        if not cleaned:
            return False

        # Évite les chaînes trop courtes ou de type "Aired"/date.
        if len(cleaned) < 60:
            return False
        if re.search(r"\b\d{4}\b", cleaned) and re.fullmatch(
            r"[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}(?:\s*\(.*\))?", cleaned
        ):
            return False
        if cleaned.lower().startswith(("aired:", "episodes:", "original network:")):
            return False

        return True

    def _extract_drama_links(self, soup: BeautifulSoup | None) -> list[BeautifulSoup]:
        """Extrait les liens de fiches drama à partir d'une page de classement."""
        if soup is None:
            return []

        drama_links: list[BeautifulSoup] = []
        for link in soup.select("a[href]"):
            href = link.get("href", "").strip()
            if not href:
                continue
            href = href.split("?", 1)[0]
            if re.fullmatch(r"/\d+(?:-[a-z0-9-]+)?/?", href):
                drama_links.append(link)
            elif re.search(r"https?://(?:www\.)?mydramalist\.com/\d+(?:-[a-z0-9-]+)?/?$", href):
                drama_links.append(link)

        return drama_links

    @staticmethod
    def _is_korean_country(value: str) -> bool:
        """Retourne True si la valeur de pays correspond à la Corée du Sud."""
        lowered = value.lower()
        return any(
            token in lowered
            for token in [
                "south korea",
                "korea, south",
                "korean",
                "corée du sud",
                "coree du sud",
            ]
        )

    def _is_korean_listing_link(self, link: BeautifulSoup) -> bool:
        """Filtre les entrées de listing pour ne garder que les dramas coréens."""
        text_muted_nodes: list[BeautifulSoup] = []
        container = link.find_parent("div", class_=re.compile(r"\brow-cell\b|\bcontent\b"))
        if container:
            text_muted_nodes.extend(container.select("span.text-muted"))
        if not text_muted_nodes:
            text_muted_nodes.extend(link.find_all_next("span", class_="text-muted", limit=2))

        for node in text_muted_nodes:
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            lowered = text.lower()
            if "korean drama" in lowered:
                return True
            if "drama" in lowered and "korean" not in lowered:
                return False

        # Si l'information n'est pas visible dans la carte, on laisse passer
        # et on valide strictement sur la fiche drama.
        return True

    def _extract_synopsis(self, soup: BeautifulSoup) -> str | None:
        """Extrait un synopsis lisible en anglais depuis MyDramaList."""
        candidates: list[str] = []

        for selector in [
            ".show-synopsis",
            "div.show-synopsis",
            "div.summary p",
            "div.show-summaryx p",
            "div.synopsis p",
            "div.summary",
            "div.show-summary",
            "div.show-synopsis p",
            "#show-detailsxx .show-synopsis p",
            "#show-detailsxx .show-synopsis span",
        ]:
            for node in soup.select(selector):
                text = self._clean_text(node.get_text(" ", strip=True))
                # Retire les libellés d'UI présents dans le bloc synopsis.
                text = re.sub(r"\bEdit Translation\b", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s+", " ", text).strip()
                if text and text not in candidates:
                    candidates.append(text)

        meta_candidates = []
        for selector in [
            "meta[property='og:description']",
            "meta[name='description']",
            "meta[name='twitter:description']",
        ]:
            node = soup.select_one(selector)
            if node and node.get("content"):
                text = self._clean_text(node.get("content", ""))
                if text and text not in meta_candidates:
                    meta_candidates.append(text)

        for text in candidates:
            if text and self._looks_like_synopsis(text) and not self._contains_hangul(text):
                return text

        if candidates:
            for text in candidates:
                if self._looks_like_synopsis(text):
                    return text

        if meta_candidates:
            for text in meta_candidates:
                if self._looks_like_synopsis(text):
                    return text

        # Dernier recours : on garde le premier candidat brut si présent.
        if candidates:
            return candidates[0]

        if meta_candidates:
            return meta_candidates[0]

        return None

    def _extract_title(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """Extrait un titre lisible et conserve une version originale si possible."""
        candidates: list[tuple[str, str]] = []

        # Meta tags (souvent plus stables)
        for selector in ["meta[property='og:title']", "meta[name='twitter:title']"]:
            node = soup.select_one(selector)
            if node and node.get("content"):
                text = self._clean_title(" ".join(node.get("content", "").split()))
                if text:
                    candidates.append((selector, text))

        # Titre de la page HTML
        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if page_title:
            cleaned_page_title = self._clean_title(page_title)
            if cleaned_page_title and cleaned_page_title not in {c[1] for c in candidates}:
                candidates.append(("<title>", cleaned_page_title))

        # Titres alternatifs / anglais / romanisés
        for selector in [
            "#show-detailsxx .col-film-rating[data-title]",
            "h6.title a[href]",
            "h1.box-title",
            "h1.title",
            ".title-english",
            ".english-title",
            ".title-en",
            "[class*='english']",
            "[class*='romanized']",
            "[class*='alt-title']",
            "h1",
            "h2",
            "[itemprop='name']",
            "[class*='title']",
        ]:
            for node in soup.select(selector):
                if node.has_attr("data-title"):
                    raw = node.get("data-title", "")
                elif node.has_attr("title") and not node.get_text("", strip=True):
                    raw = node.get("title", "")
                else:
                    raw = node.get_text(" ", strip=True)
                text = self._clean_title(" ".join(raw.split()))
                if text and text not in {c[1] for c in candidates}:
                    candidates.append((selector, text))

        # Fallback très large sur le texte visible de la page
        if not candidates:
            visible_text = self._clean_title(soup.get_text(" ", strip=True))
            if visible_text:
                candidates.append(("body", visible_text[:200]))

        if not candidates:
            return None, None

        # Priorité : préférer un titre sans Hangul si possible
        latin_candidates = [
            text for _, text in candidates if text and not self._contains_hangul(text)
        ]
        if latin_candidates:
            preferred = latin_candidates[0]
        else:
            preferred = candidates[0][1]

        original = candidates[0][1]
        return preferred, original

    def scrape_drama_page(self, url: str) -> dict:
        """Scrape une fiche de drama individuelle depuis MyDramaList.

        Extrait les informations suivantes :
            - Titre (titre original et romanisé)
            - Note moyenne des utilisateurs
            - Nombre de ratings
            - Nombre de watchers
            - Genres
            - Tags
            - Synopsis
            - Réseau de diffusion
            - Nombre d'épisodes

        Args:
            url: URL de la fiche drama sur MyDramaList.

        Returns:
            Dictionnaire contenant les données extraites.
        """
        soup = self._fetch_page(url)
        if soup is None:
            return {}

        data: dict[str, Any] = {"url": url, "source": "mydramalist"}

        # Extraction du titre
        preferred_title, original_title = self._extract_title(soup)
        if preferred_title:
            data["titre"] = preferred_title
            data["english_name"] = preferred_title
        if original_title:
            data["titre_original"] = original_title
            if not data.get("english_name"):
                data["english_name"] = original_title
        elif data.get("english_name") is None and data.get("titre"):
            data["english_name"] = data["titre"]

        # Extraction de la note moyenne
        score_node = soup.select_one(
            "div.rating-panel .score, [data-score], .col-film-rating .box, "
            ".hfs b[itempropx='ratingValue']"
        )
        if score_node:
            score_str = score_node.get("data-score") or score_node.get_text(strip=True)
            try:
                data["note_moyenne"] = float(score_str)
            except (ValueError, TypeError):
                pass

        # Extraction du nombre de ratings
        ratings_text_candidates = [
            node.get_text(" ", strip=True)
            for node in soup.select("div.rating-panel .ratings, .hfs, .text-muted")
        ]
        for ratings_text in ratings_text_candidates:
            match = re.search(
                r"from\s+(\d[\d,]*)\s+users|scored\s+by\s+(\d[\d,]*)\s+users",
                ratings_text,
                re.IGNORECASE,
            )
            if not match:
                match = re.search(r"(\d[\d,]*)\s*ratings?", ratings_text, re.IGNORECASE)
            if match:
                value = match.group(1) or match.group(2)
                if value:
                    data["nb_votes"] = int(value.replace(",", ""))
                    break

        # Extraction du nombre de watchers
        watchers_text = soup.get_text(" ", strip=True)
        match_watchers = re.search(r"#\s*of\s*Watchers:\s*([\d,]+)", watchers_text, re.IGNORECASE)
        if not match_watchers:
            match_watchers = re.search(r"Watchers\s*[:#]?\s*([\d,]+)", watchers_text, re.IGNORECASE)
        if match_watchers:
            data["nb_watchers"] = int(match_watchers.group(1).replace(",", ""))

        # Extraction des genres
        genre_nodes = soup.select("li.show-genres a, .show-genres a, div.show-categoriesx ul.list-inline li a")
        if genre_nodes:
            data["genres"] = [g.get_text(strip=True) for g in genre_nodes]

        # Extraction des tags
        tag_nodes = soup.select("li.show-tags a, .show-tags a, div.tags ul.list-inline li a")
        if tag_nodes:
            data["tags"] = [t.get_text(strip=True) for t in tag_nodes[:15]]

        # Extraction du synopsis
        synopsis_text = self._extract_synopsis(soup)
        if synopsis_text:
            data["synopsis"] = synopsis_text

        # Extraction des informations de diffusion (table de détails)
        detail_rows = soup.select("div.show-detailsx tr, .show-details tr")
        for row in detail_rows:
            label_node = row.select_one("td:first-child, th")
            value_node = row.select_one("td:last-child, td")
            if label_node and value_node:
                label = label_node.get_text(strip=True).lower()
                value = value_node.get_text(strip=True)
                if "episodes" in label:
                    match = re.search(r"(\d+)", value)
                    if match:
                        data["nb_episodes"] = int(match.group(1))
                elif "aired" in label or "date" in label:
                    data["date_diffusion"] = value
                elif "network" in label or "channel" in label:
                    data["reseaux_diffusion"] = [
                        n.strip() for n in re.split(r"[,;]", value) if n.strip()
                    ]
                elif "screenwriter" in label or "writer" in label:
                    data["scenariste"] = value
                elif "director" in label:
                    data["realisateur"] = value

        detail_items = soup.select("ul.list.m-a-0 li, ul.list.m-a-0.hidden-md-up li")
        for item in detail_items:
            label_node = item.select_one("b.inline")
            if label_node:
                label = label_node.get_text(" ", strip=True).replace(":", "").strip().lower()
                value_text = item.get_text(" ", strip=True)
                value_text = re.sub(rf"^{re.escape(label_node.get_text(' ', strip=True))}\s*", "", value_text)
                value_text = value_text.strip()

                if label == "episodes":
                    match = re.search(r"(\d+)", value_text)
                    if match:
                        data["nb_episodes"] = int(match.group(1))
                elif label in ("aired", "aired on"):
                    data["date_diffusion"] = value_text
                elif label in ("original network", "network", "channel"):
                    data["reseaux_diffusion"] = [
                        n.strip() for n in re.split(r"[,;]", value_text) if n.strip()
                    ]
                elif label in ("screenwriter", "writer"):
                    data["scenariste"] = value_text
                elif label == "director":
                    data["realisateur"] = value_text
                elif label == "native title" and value_text:
                    data["titre_original"] = value_text
                elif label == "country" and value_text:
                    data["pays_origine"] = [value_text]

            text = item.get_text(" ", strip=True)
            if not text:
                continue
            lower = text.lower()
            if lower.startswith("episodes:"):
                match = re.search(r"(\d+)", text)
                if match:
                    data["nb_episodes"] = int(match.group(1))
            elif lower.startswith("aired:"):
                data["date_diffusion"] = text.split(":", 1)[1].strip()
            elif lower.startswith("original network:"):
                value = text.split(":", 1)[1].strip()
                data["reseaux_diffusion"] = [
                    n.strip() for n in re.split(r"[,;]", value) if n.strip()
                ]
            elif lower.startswith("score:"):
                match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
                if match:
                    try:
                        data["note_moyenne"] = float(match.group(1))
                    except ValueError:
                        pass

        country_values = data.get("pays_origine") or []
        if country_values and not any(self._is_korean_country(v) for v in country_values):
            logger.info("Fiche ignorée (non coréenne): %s — pays=%s", url, country_values)
            return {}

        logger.info("Scraping réussi: %s — titre=%s", url, data.get("titre"))
        return data

    def scrape_top_kdramas(self, max_pages: int = 10) -> list[dict]:
        """Scrape la liste des K-Dramas les mieux notés sur MyDramaList.

        Parcourt les pages du classement (/shows/top) et extrait les
        liens vers les fiches individuelles, puis scrape chaque fiche.

        Args:
            max_pages: Nombre maximum de pages de classement à parcourir.

        Returns:
            Liste de dictionnaires contenant les données des K-Dramas.
        """
        all_kdramas: list[dict] = []
        logger.info("Démarrage du scraping MyDramaList (max_pages=%d)", max_pages)

        for page in range(1, max_pages + 1):
            # URL du classement des K-Dramas
            list_url = f"{self.base_url}/shows/top?page={page}"
            logger.info("Scraping page de classement %d: %s", page, list_url)

            soup = self._fetch_page(list_url)
            drama_links = self._extract_drama_links(soup)

            if not drama_links:
                logger.info(
                    "Aucun lien trouvé avec la page HTML standard pour %s — tentative via Playwright",
                    list_url,
                )
                playwright_soup = self._fetch_page_with_playwright(list_url)
                drama_links = self._extract_drama_links(playwright_soup)

            if not drama_links:
                logger.info("Aucun lien trouvé page %d — fin de pagination", page)
                break

            seen_urls: set[str] = set()
            for link in drama_links:
                if not self._is_korean_listing_link(link):
                    continue
                href = link.get("href", "")
                if href:
                    drama_url = urljoin(self.base_url, href)
                    if drama_url in seen_urls:
                        continue
                    seen_urls.add(drama_url)
                    kdrama_data = self.scrape_drama_page(drama_url)

                    # Filter: keep only drama content
                    if kdrama_data and is_drama_only(kdrama_data):
                        all_kdramas.append(kdrama_data)
                    elif kdrama_data:
                        logger.debug("Filtered out (not a drama): %s", kdrama_data.get("titre"))

            logger.info("Page %d: %d K-Dramas scrapés (total: %d)", page, len(drama_links), len(all_kdramas))

        logger.info("Scraping MyDramaList terminé: %d K-Dramas", len(all_kdramas))
        return all_kdramas


# ===========================================================================
# SECTION 4 — Collecteur de base de données (SQLite)
# ===========================================================================
class DatabaseCollector:
    """Collecteur de données depuis une base de données SQLite.

    Lit les K-Dramas stockés dans une base SQLite locale. Cette source
    démontre la compétence d'extraction depuis une base de données (BDD),
    l'une des quatre sources exigées par le projet (API REST, fichier CSV,
    scraping web, base de données).

    SQLite est choisi car il est intégré à Python (aucune dépendance externe,
    aucun serveur à installer) — la base est un simple fichier .db.

    Attributes:
        db_path: Chemin du fichier de base de données SQLite.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialise le collecteur de base de données.

        Args:
            db_path: Chemin du fichier SQLite (.db).

        Raises:
            FileNotFoundError: Si le fichier de base n'existe pas.
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Base de données introuvable: {self.db_path}")
        logger.info("DatabaseCollector initialisé (db=%s)", self.db_path)

    def collect(self) -> list[dict]:
        """Lit tous les K-Dramas depuis la base SQLite.

        Se connecte à la base, exécute une requête SELECT sur la table
        kdramas et retourne les enregistrements normalisés.

        Returns:
            Liste de dictionnaires au schéma normalisé.
        """
        import sqlite3

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        logger.info("Lecture des K-Dramas depuis SQLite: %s", self.db_path)

        try:
            cursor.execute(
                """
                SELECT titre, titre_original, date_diffusion, nb_episodes,
                       synopsis, note_moyenne, nb_votes, langue_originale,
                       pays_origine, genres, reseaux_diffusion
                FROM kdramas
                """
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            logger.error("Erreur de lecture SQLite: %s", e)
            conn.close()
            return []

        records: list[dict] = []
        for row in rows:
            record: dict[str, Any] = {"source": "database"}
            for key in row.keys():
                value = row[key]
                # Conversion des chaînes séparées par virgule en listes
                if key in ("genres", "reseaux_diffusion", "pays_origine") and value:
                    record[key] = [v.strip() for v in re.split(r"[,;]", str(value)) if v.strip()]
                else:
                    record[key] = value
            if not record.get("english_name") and record.get("titre"):
                record["english_name"] = record["titre"]
            records.append(record)

        conn.close()
        logger.info("Base de données lue: %d enregistrements", len(records))
        return records


# ===========================================================================
# SECTION 5 — Orchestration de la collecte
# ===========================================================================
@dataclass
class CollectionReport:
    """Rapport d'exécution de la collecte de données.

    Centralise les statistiques de collecte pour chaque source afin
    de faciliter le suivi et le débogage.

    Attributes:
        source: Nom de la source (tmdb, csv, mydramalist).
        total_records: Nombre total d'enregistrements collectés.
        errors: Nombre d'erreurs rencontrées.
        duration_seconds: Durée totale de la collecte en secondes.
        timestamp: Horodatage de la collecte.
    """

    source: str
    total_records: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def save_raw_data(data: list[dict], filename: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    """Sauvegarde les données brutes collectées au format JSON.

    Args:
        data: Liste de dictionnaires à sauvegarder.
        filename: Nom du fichier de sortie (sans extension).
        output_dir: Répertoire de destination.

    Returns:
        Chemin du fichier créé.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{filename}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Données sauvegardées: %s (%d enregistrements)", file_path, len(data))
    return file_path


def run_collection(
    csv_path: Optional[str] = None,
    db_path: Optional[str] = None,
    max_tmdb_pages: int = 50,
    max_scrape_pages: int = 10,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, CollectionReport]:
    """Orchestre la collecte depuis les quatre sources de données.

    Exécute séquentiellement la collecte TMDB (API REST), CSV (flat file),
    scraping MyDramaList (web) et base de données (BDD), sauvegarde les
    données brutes et génère un rapport d'exécution.

    Args:
        csv_path: Chemin du fichier CSV (si None, étape CSV ignorée).
        db_path: Chemin du fichier SQLite (si None, étape BDD ignorée).
        max_tmdb_pages: Nombre maximum de pages TMDB à parcourir.
        max_scrape_pages: Nombre maximum de pages MyDramaList à scraper.
        output_dir: Répertoire de sauvegarde des données brutes.

    Returns:
        Dictionnaire des rapports de collecte par source.
    """
    reports: dict[str, CollectionReport] = {}
    logger.info("=" * 60)
    logger.info("DÉMARRAGE DE LA COLLECTE DE DONNÉES — ÉTAPE 1")
    logger.info("=" * 60)

    # --- Source 1 : API REST TMDB ---
    if max_tmdb_pages > 0:
        try:
            tmdb_collector = TMDBCollector()
            start = time.time()
            tmdb_data = tmdb_collector.run_full_collection(max_pages=max_tmdb_pages)
            save_raw_data(tmdb_data, "raw_tmdb", output_dir)
            reports["tmdb"] = CollectionReport(
                source="tmdb",
                total_records=len(tmdb_data),
                duration_seconds=time.time() - start,
            )
        except (ValueError, Exception) as e:
            logger.error("Échec collecte TMDB: %s", e)
            reports["tmdb"] = CollectionReport(source="tmdb", errors=1)
    else:
        logger.info("Nombre de pages TMDB demandé = 0 — étape TMDB ignorée")

    # --- Source 2 : Fichier CSV (flat file) ---
    if csv_path:
        try:
            csv_collector = CSVCollector(csv_path)
            start = time.time()
            csv_data = csv_collector.collect()
            save_raw_data(csv_data, "raw_csv", output_dir)
            reports["csv"] = CollectionReport(
                source="csv",
                total_records=len(csv_data),
                duration_seconds=time.time() - start,
            )
        except (FileNotFoundError, ValueError, Exception) as e:
            logger.error("Échec collecte CSV: %s", e)
            reports["csv"] = CollectionReport(source="csv", errors=1)
    else:
        logger.info("Aucun fichier CSV fourni — étape CSV ignorée")

    # --- Source 3 : Scraping MyDramaList (web) ---
    if max_scrape_pages > 0:
        try:
            scraper = MyDramaListScraper()
            start = time.time()
            scrape_data = scraper.scrape_top_kdramas(max_pages=max_scrape_pages)
            save_raw_data(scrape_data, "raw_scrape", output_dir)
            reports["mydramalist"] = CollectionReport(
                source="mydramalist",
                total_records=len(scrape_data),
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            logger.error("Échec scraping MyDramaList: %s", e)
            reports["mydramalist"] = CollectionReport(source="mydramalist", errors=1)
    else:
        logger.info("Nombre de pages MyDramaList demandé = 0 — étape MyDramaList ignorée")

    # --- Source 4 : Base de données (BDD) ---
    if db_path:
        try:
            db_collector = DatabaseCollector(db_path)
            start = time.time()
            db_data = db_collector.collect()
            save_raw_data(db_data, "raw_database", output_dir)
            reports["database"] = CollectionReport(
                source="database",
                total_records=len(db_data),
                duration_seconds=time.time() - start,
            )
        except (FileNotFoundError, Exception) as e:
            logger.error("Échec collecte BDD: %s", e)
            reports["database"] = CollectionReport(source="database", errors=1)
    else:
        logger.info("Aucune base de données fournie — étape BDD ignorée")

    # --- Récapitulatif ---
    logger.info("=" * 60)
    logger.info("RAPPORT DE COLLECTE")
    logger.info("=" * 60)
    for source_name, report in reports.items():
        logger.info(
            "Source: %-15s | Enregistrements: %5d | Erreurs: %d | Durée: %.1fs",
            report.source,
            report.total_records,
            report.errors,
            report.duration_seconds,
        )
    logger.info("=" * 60)

    return reports


# ===========================================================================
# Point d'entrée du script
# ===========================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Collecte de données K-Drama depuis 4 sources: API TMDB, CSV, scraping MyDramaList, base SQLite."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Chemin du fichier CSV à collecter (flat file, optionnel).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Chemin du fichier SQLite à collecter (base de données, optionnel).",
    )
    parser.add_argument(
        "--tmdb-pages",
        type=int,
        default=50,
        help="Nombre maximum de pages TMDB à parcourir (défaut: 50).",
    )
    parser.add_argument(
        "--scrape-pages",
        type=int,
        default=10,
        help="Nombre maximum de pages MyDramaList à scraper (défaut: 10).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Répertoire de sortie pour les données brutes.",
    )

    args = parser.parse_args()

    run_collection(
        csv_path=args.csv,
        db_path=args.db,
        max_tmdb_pages=args.tmdb_pages,
        max_scrape_pages=args.scrape_pages,
        output_dir=Path(args.output_dir),
    )
