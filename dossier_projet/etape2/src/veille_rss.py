#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
veille_rss.py — Agrégateur RSS pour la veille technique et réglementaire.

Ce script automatise la collecte, le filtrage et la synthèse d'articles
publiés sur des flux RSS liés à l'intelligence artificielle, à la
réglementation (RGPD, AI Act, PIPA) et aux technologies de recommandation.

Fonctionnalités :
  - Lecture multi-sources (flux RSS prédéfinis par catégorie).
  - Filtrage par mots-clés pertinents pour le projet K-Drama RecSys.
  - Déduplication des articles (historique persistant en JSON).
  - Génération d'un rapport Markdown trié par date et par catégorie.
  - Gestion d'erreurs robuste (un flux indisponible ne bloque pas les autres).
  - Journalisation (logging) configurable par niveau.

Compétence : C6 — Organisation de la veille technique et réglementaire.

Auteur : Équipe projet RNCP — K-Drama Recommendation System
Date : 2025
Licence : MIT
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

import feedparser  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("veille_rss")


# ---------------------------------------------------------------------------
# Constantes et configuration
# ---------------------------------------------------------------------------

# Répertoire de travail : là où sont stockés l'historique et le rapport.
BASE_DIR: Path = Path(__file__).resolve().parent

# Fichier d'historique (pour la déduplication et le suivi longitudinal).
HISTORIQUE_FILE: Path = BASE_DIR / "veille_historique.json"

# Fichier de rapport généré (Markdown).
RAPPORT_FILE: Path = BASE_DIR / "rapport_veille.md"

# Nombre maximum d'articles à afficher par catégorie dans le rapport.
MAX_ARTICLES_PAR_CATEGORIE: int = 20

# Mots-clés de filtrage (insensibles à la casse et aux accents).
MOTS_CLES: List[str] = [
    "intelligence artificielle",
    "ia",
    "ai",
    "machine learning",
    "deep learning",
    "recommandation",
    "recommendation",
    "recommender",
    "embeddings",
    "sentence-transformers",
    "transformers",
    "nlp",
    "natural language",
    "rgpd",
    "gdpr",
    "ai act",
    "pia",
    "pipa",
    "cnil",
    "privacy",
    "vie privée",
    "données personnelles",
    "hugging face",
    "openai",
    "cohere",
    "llm",
    "large language model",
    "bert",
    "svd",
    "collaborative filtering",
    "content-based",
    "k-drama",
    "korea",
    "corée",
    "réglementation",
    "ethique",
    "ethics",
    "biais",
    "bias",
    "fairness",
    "transparency",
    "mlops",
]


# Flux RSS surveillés, organisés par catégorie.
# Chaque catégorie correspond à un domaine du périmètre de veille.
FLUX_RSS: Dict[str, List[str]] = {
    "A — Modèles et recherche en IA": [
        "https://huggingface.co/blog/feed.xml",
        "https://openai.com/research/rss.xml",
        "https://towardsdatascience.com/feed",
        "https://thegradient.pub/rss/",
        # arXiv cs.IR (Information Retrieval) — flux quotidien
        "http://export.arxiv.org/rss/cs.IR",
    ],
    "B — Services d'IA et API": [
        # Blog OpenAI (changements d'API, tarification)
        "https://openai.com/blog/rss.xml",
        # Blog Cohere
        "https://txt.cohere.com/rss/",
        # Google Cloud AI
        "https://cloud.google.com/blog/products/ai-machine-learning/rss",
        # AWS Machine Learning
        "https://aws.amazon.com/blogs/machine-learning/feed/",
    ],
    "C — Réglementation et éthique": [
        # CNIL — flux général (filtré par mots-clés IA)
        "https://www.cnil.fr/fr/rss.xml",
        # EDPB — actualités
        "https://www.edpb.europa.eu/news/news_en.rss",
        # Future of Life Institute — AI policy
        "https://futureoflife.org/feed/",
        # artificialintelligenceact.eu
        "https://artificialintelligenceact.eu/feed/",
    ],
    "D — Communauté et retours d'expérience": [
        "https://news.ycombinator.com/rss",
        "https://www.reddit.com/r/MachineLearning/.rss",
        "https://www.reddit.com/r/LocalLLaMA/.rss",
    ],
}


# ---------------------------------------------------------------------------
# Modèles de données
# ---------------------------------------------------------------------------

@dataclass
class Article:
    """Représente un article collecté depuis un flux RSS.

    Attributes:
        titre: Titre de l'article.
        lien: URL de l'article.
        resume: Résumé ou extrait (description RSS).
        date_publication: Date de publication (objet datetime ou chaîne brute).
        source: Nom du flux source.
        categorie: Catégorie de veille (A, B, C ou D).
    """

    titre: str
    lien: str
    resume: str
    date_publication: str
    source: str
    categorie: str

    def hash(self) -> str:
        """Calcule un hash SHA-256 du couple (titre, lien) pour la déduplication.

        Returns:
            Chaîne hexadécimale du hash.
        """
        contenu = f"{self.titre.strip()}|{self.lien.strip()}"
        return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def _normaliser_texte(texte: str) -> str:
    """Normalise un texte pour la comparaison : minuscules, sans accents.

    Args:
        texte: Texte brut à normaliser.

    Returns:
        Texte normalisé (minuscules, sans accents, sans balises HTML).
    """
    if not texte:
        return ""
    # Suppression des balises HTML éventuelles
    texte_sans_html = re.sub(r"<[^>]+>", "", texte)
    # Suppression des accents
    texte_sans_accents = texte_sans_html.translate(str.maketrans(
        "àâäéèêëîïôöùûüç",
        "aaaeeeeiioouuuc",
    ))
    return texte_sans_accents.lower()


def _contient_mot_cle(texte: str, mots_cles: List[str]) -> bool:
    """Vérifie si un texte contient au moins un des mots-clés recherchés.

    La comparaison est insensible à la casse et aux accents.

    Args:
        texte: Texte à analyser.
        mots_cles: Liste des mots-clés à rechercher.

    Returns:
        True si au moins un mot-clé est présent, False sinon.
    """
    texte_normalise = _normaliser_texte(texte)
    for mot in mots_cles:
        if _normaliser_texte(mot) in texte_normalise:
            return True
    return False


def _formater_date(date_raw: str) -> str:
    """Tente de formater une date RSS en chaîne lisible (YYYY-MM-DD).

    Args:
        date_raw: Date brute telle que fournie par feedparser.

    Returns:
        Date formatée ou la chaîne brute si le parsing échoue.
    """
    if not date_raw:
        return "Date inconnue"
    try:
        # feedparser fournit souvent une structure time.struct_time
        struct = feedparser._parse_date(date_raw)  # type: ignore[attr-defined]
        if struct:
            dt = datetime(*struct[:6], tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return date_raw


# ---------------------------------------------------------------------------
# Gestion de l'historique (déduplication)
# ---------------------------------------------------------------------------

def _charger_historique(chemin: Path) -> Set[str]:
    """Charge l'historique des hashes d'articles déjà collectés.

    Args:
        chemin: Chemin du fichier JSON d'historique.

    Returns:
        Ensemble de hashes déjà vus.
    """
    if not chemin.exists():
        logger.info("Aucun historique trouvé — création d'un nouvel historique.")
        return set()
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            data = json.load(f)
        hashes = set(data.get("hashes", []))
        logger.info("Historique chargé : %d articles déjà vus.", len(hashes))
        return hashes
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Erreur lors du chargement de l'historique (%s). "
                       "Reprise à zéro.", e)
        return set()


def _sauvegarder_historique(chemin: Path, hashes: Set[str]) -> None:
    """Sauvegarde l'historique des hashes dans un fichier JSON.

    Args:
        chemin: Chemin du fichier JSON d'historique.
        hashes: Ensemble de hashes à sauvegarder.
    """
    data = {
        "date_maj": datetime.now(timezone.utc).isoformat(),
        "total_articles": len(hashes),
        "hashes": sorted(list(hashes)),
    }
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Historique sauvegardé : %d articles au total.", len(hashes))
    except IOError as e:
        logger.error("Impossible de sauvegarder l'historique : %s", e)


# ---------------------------------------------------------------------------
# Collecte des articles
# ---------------------------------------------------------------------------

def _parser_flux(url: str, categorie: str) -> List[Article]:
    """Parse un flux RSS et retourne la liste des articles.

    Gère les erreurs de réseau et de parsing de manière isolée :
    un flux indisponible ne lève pas d'exception fatale.

    Args:
        url: URL du flux RSS.
        categorie: Catégorie de veille associée au flux.

    Returns:
        Liste des articles collectés (vide si le flux est indisponible).
    """
    try:
        logger.debug("Lecture du flux : %s", url)
        flux = feedparser.parse(url)

        if flux.bozo and flux.bozo_exception:
            logger.warning("Flux malformé (%s) : %s", url, flux.bozo_exception)

        if not flux.entries:
            logger.warning("Aucune entrée trouvée pour le flux : %s", url)
            return []

        articles: List[Article] = []
        for entree in flux.entries:
            titre = entree.get("title", "Sans titre")
            lien = entree.get("link", "")
            resume = entree.get("summary", entree.get("description", ""))
            date_raw = entree.get("published", entree.get("updated", ""))

            # Extraction du nom de la source à partir de l'URL ou du flux
            source = (
                flux.feed.get("title", url)
                if hasattr(flux, "feed")
                else url
            )

            article = Article(
                titre=titre,
                lien=lien,
                resume=resume,
                date_publication=_formater_date(date_raw),
                source=source,
                categorie=categorie,
            )
            articles.append(article)

        logger.info("Flux '%s' : %d articles collectés.", url, len(articles))
        return articles

    except Exception as e:
        logger.error("Erreur lors de la lecture du flux %s : %s", url, e)
        return []


def collecter_articles(
    flux_rss: Dict[str, List[str]],
    mots_cles: List[str],
    hashes_deja_vus: Set[str],
) -> List[Article]:
    """Collecte tous les articles des flux RSS, filtre et déduplique.

    Args:
        flux_rss: Dictionnaire {catégorie: [urls de flux]}.
        mots_cles: Liste des mots-clés pour le filtrage.
        hashes_deja_vus: Ensemble des hashes déjà collectés (déduplication).

    Returns:
        Liste des nouveaux articles pertinents, non dupliqués.
    """
    tous_articles: List[Article] = []
    nouveaux_hashes: Set[str] = set(hashes_deja_vus)

    for categorie, urls in flux_rss.items():
        logger.info("=== Catégorie : %s ===", categorie)
        for url in urls:
            articles_flux = _parser_flux(url, categorie)
            for article in articles_flux:
                # Déduplication
                h = article.hash()
                if h in nouveaux_hashes:
                    continue
                # Filtrage par mots-clés (sur titre + résumé)
                texte_complet = f"{article.titre} {article.resume}"
                if not _contient_mot_cle(texte_complet, mots_cles):
                    continue
                # Article pertinent et nouveau
                tous_articles.append(article)
                nouveaux_hashes.add(h)

    logger.info("Total : %d nouveaux articles pertinents collectés.",
                len(tous_articles))
    return tous_articles


# ---------------------------------------------------------------------------
# Génération du rapport Markdown
# ---------------------------------------------------------------------------

def generer_rapport(
    articles: List[Article],
    chemin_rapport: Path,
    date_generation: Optional[str] = None,
) -> None:
    """Génère un rapport Markdown des articles collectés, trié par catégorie.

    Args:
        articles: Liste des articles à inclure dans le rapport.
        chemin_rapport: Chemin du fichier Markdown à générer.
        date_generation: Date de génération (par défaut : maintenant).
    """
    if date_generation is None:
        date_generation = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d à %H:%M UTC"
        )

    lignes: List[str] = []
    lignes.append("# Rapport de veille technique et réglementaire")
    lignes.append("")
    lignes.append(f"**Généré le** : {date_generation}")
    lignes.append(f"**Nombre d'articles** : {len(articles)}")
    lignes.append("**Projet** : K-Drama Recommendation System")
    lignes.append("")
    lignes.append("---")
    lignes.append("")

    # Regroupement par catégorie
    par_categorie: Dict[str, List[Article]] = {}
    for article in articles:
        par_categorie.setdefault(article.categorie, []).append(article)

    for categorie in sorted(par_categorie.keys()):
        articles_cat = par_categorie[categorie]
        lignes.append(f"## {categorie}")
        lignes.append("")
        lignes.append(f"_{len(articles_cat)} article(s) pertinents_")
        lignes.append("")

        # Tri par date décroissante (les dates inconnues en dernier)
        articles_tries = sorted(
            articles_cat,
            key=lambda a: a.date_publication,
            reverse=True,
        )

        for i, article in enumerate(articles_tries[:MAX_ARTICLES_PAR_CATEGORIE], 1):
            lignes.append(f"### {i}. {article.titre}")
            lignes.append("")
            lignes.append(f"- **Date** : {article.date_publication}")
            lignes.append(f"- **Source** : {article.source}")
            lignes.append(f"- **Lien** : {article.lien}")
            # Résumé tronqué à 300 caractères pour la lisibilité
            resume = article.resume.strip()
            if len(resume) > 300:
                resume = resume[:300] + "..."
            lignes.append(f"- **Résumé** : {resume}")
            lignes.append("")

        lignes.append("---")
        lignes.append("")

    try:
        with open(chemin_rapport, "w", encoding="utf-8") as f:
            f.write("\n".join(lignes))
        logger.info("Rapport généré : %s", chemin_rapport)
    except IOError as e:
        logger.error("Impossible d'écrire le rapport : %s", e)


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def main() -> int:
    """Point d'entrée principal du script de veille RSS.

    Étapes :
      1. Chargement de l'historique (déduplication).
      2. Collecte des articles sur tous les flux configurés.
      3. Filtrage par mots-clés et déduplication.
      4. Génération du rapport Markdown.
      5. Sauvegarde de l'historique mis à jour.

    Returns:
        0 en cas de succès, 1 en cas d'erreur fatale.
    """
    logger.info("=" * 60)
    logger.info("Démarrage de la veille RSS — K-Drama RecSys")
    logger.info("=" * 60)

    try:
        # 1. Chargement de l'historique
        hashes_existants = _charger_historique(HISTORIQUE_FILE)

        # 2 & 3. Collecte et filtrage
        articles = collecter_articles(FLUX_RSS, MOTS_CLES, hashes_existants)

        if not articles:
            logger.info("Aucun nouvel article pertinent trouvé cette fois-ci.")
            # On génère tout de même un rapport (vide) pour tracer l'exécution.
            generer_rapport([], RAPPORT_FILE)
            return 0

        # 4. Génération du rapport
        generer_rapport(articles, RAPPORT_FILE)

        # 5. Sauvegarde de l'historique
        # On recalcule tous les hashes (existants + nouveaux) pour persister
        tous_hashes = set(hashes_existants)
        for article in articles:
            tous_hashes.add(article.hash())
        _sauvegarder_historique(HISTORIQUE_FILE, tous_hashes)

        logger.info("Veille terminée avec succès. %d nouveaux articles.",
                    len(articles))
        return 0

    except KeyboardInterrupt:
        logger.warning("Interruption par l'utilisateur (Ctrl+C).")
        return 1
    except Exception as e:
        logger.error("Erreur fatale lors de la veille : %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
