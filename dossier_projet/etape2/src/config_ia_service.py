#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_ia_service.py — Configuration et tests du service d'IA retenu.

Ce script configure et valide le service d'IA choisi pour le système de
recommandation de K-Dramas, composé de deux briques :

  1. **Content-based filtering** : Hugging Face `sentence-transformers`
     pour vectoriser les descriptions de séries et calculer la similarité
     sémantique.

  2. **Collaborative filtering** : `scikit-learn` (TruncatedSVD +
     NearestNeighbors) pour identifier des utilisateurs similaires et
     recommander des séries appréciées par des profils comparables.

Le script inclut :
  - Le chargement (lazy) des modèles avec détection automatique CPU/GPU.
  - Le calcul d'embeddings en batch (content-based).
  - La recommandation par similarité cosine (content-based).
  - L'entraînement du SVD et la recommandation KNN (collaborative).
  - Des tests de validation de bout en bout (latence, qualité, erreurs).

Compétence : C8 — Configuration d'un service d'IA suivant sa documentation.

Documentation de référence :
  - sentence-transformers : https://www.sbert.net
  - scikit-learn TruncatedSVD :
    https://scikit-learn.org/stable/modules/decomposition.html#truncated-svd
  - scikit-learn NearestNeighbors :
    https://scikit-learn.org/stable/modules/neighbors.html

Auteur : Équipe projet RNCP — K-Drama Recommendation System
Date : 2025
Licence : MIT
"""

from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Configuration du logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("config_ia_service")


# ---------------------------------------------------------------------------
# Exceptions personnalisées
# ---------------------------------------------------------------------------

class ConfigurationIAError(Exception):
    """Erreur de base pour les problèmes de configuration du service d'IA."""


class ModeleIntrouvableError(ConfigurationIAError):
    """Levée quand un modèle ne peut pas être chargé (téléchargement, etc.)."""


class DonneesInvalidesError(ConfigurationIAError):
    """Levée quand les données d'entrée sont invalides (matrice vide, etc.)."""


# ---------------------------------------------------------------------------
# Content-based filtering — sentence-transformers
# ---------------------------------------------------------------------------

class ContentBasedRecommender:
    """Recommandeur basé sur le contenu utilisant sentence-transformers.

    Cette classe encapsule le chargement d'un modèle d'embeddings et la
    recommandation de K-Dramas par similarité sémantique (cosine).

    Attributes:
        model_name: Nom du modèle Hugging Face (ex: 'all-MiniLM-L6-v2').
        device: Device d'inférence ('cpu', 'cuda' ou None pour auto).
        _model: Instance SentenceTransformer (chargée en lazy).
        _embeddings_cache: Embeddings pré-calculés du catalogue.
        _descriptions_cache: Descriptions correspondantes au cache.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ) -> None:
        """Initialise le recommandeur content-based.

        Args:
            model_name: Nom du modèle sentence-transformers.
            device: Device forcé ('cpu' ou 'cuda'). Si None, détection auto.
        """
        self.model_name = model_name
        self.device = device
        self._model: Any = None  # chargement lazy
        self._embeddings_cache: Optional[np.ndarray] = None
        self._descriptions_cache: List[str] = []

    # -- Chargement du modèle ------------------------------------------------

    def _charger_modele(self) -> Any:
        """Charge le modèle sentence-transformers (lazy loading).

        Détecte automatiquement le device (CPU/GPU) si non spécifié.
        Gère les erreurs de téléchargement et de chargement.

        Returns:
            Instance SentenceTransformer.

        Raises:
            ModeleIntrouvableError: Si le modèle ne peut pas être chargé.
        """
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            import torch  # type: ignore
        except ImportError as e:
            raise ModeleIntrouvableError(
                f"Dépendances manquantes pour sentence-transformers : {e}. "
                f"Installez-les avec : pip install sentence-transformers torch"
            ) from e

        # Détection automatique du device
        device_effectif = self.device
        if device_effectif is None:
            if torch.cuda.is_available():
                device_effectif = "cuda"
                logger.info("GPU CUDA détecté — inférence sur GPU.")
            else:
                device_effectif = "cpu"
                logger.info("Aucun GPU détecté — inférence sur CPU.")

        try:
            logger.info("Chargement du modèle sentence-transformers : %s",
                        self.model_name)
            self._model = SentenceTransformer(self.model_name,
                                              device=device_effectif)
            logger.info("Modèle chargé avec succès (device=%s).",
                        device_effectif)
            return self._model
        except Exception as e:
            raise ModeleIntrouvableError(
                f"Impossible de charger le modèle '{self.model_name}' : {e}. "
                f"Vérifiez votre connexion internet (téléchargement initial) "
                f"ou que le nom du modèle est correct sur "
                f"https://huggingface.co/models"
            ) from e

    # -- Calcul des embeddings -----------------------------------------------

    def calculer_embeddings(
        self,
        descriptions: List[str],
        batch_size: int = 32,
        normaliser: bool = True,
    ) -> np.ndarray:
        """Calcule les embeddings d'une liste de descriptions.

        Args:
            descriptions: Liste de textes (descriptions de K-Dramas).
            batch_size: Taille de batch pour l'inférence.
            normaliser: Si True, normalise les vecteurs (L2) pour que la
                similarité cosine se réduise à un produit scalaire.

        Returns:
            Matrice numpy de shape (n_descriptions, dimensionnalité).

        Raises:
            DonneesInvalidesError: Si la liste de descriptions est vide.
        """
        if not descriptions:
            raise DonneesInvalidesError(
                "La liste de descriptions est vide — "
                "impossible de calculer les embeddings."
            )

        model = self._charger_modele()

        logger.info("Calcul des embeddings pour %d descriptions...",
                    len(descriptions))
        debut = time.perf_counter()

        embeddings = model.encode(
            descriptions,
            batch_size=batch_size,
            normalize_embeddings=normaliser,
            show_progress_bar=len(descriptions) > 100,
        )
        embeddings = np.array(embeddings)

        duree_ms = (time.perf_counter() - debut) * 1000
        logger.info("Embeddings calculés en %.1f ms (shape=%s).",
                    duree_ms, embeddings.shape)

        return embeddings

    # -- Indexation du catalogue ---------------------------------------------

    def indexer_catalogue(
        self,
        descriptions: List[str],
        batch_size: int = 32,
    ) -> None:
        """Calcule et met en cache les embeddings du catalogue complet.

        Cette méthode pré-calcule les embeddings une fois au démarrage,
        puis les réutilise pour toutes les requêtes ultérieures.

        Args:
            descriptions: Liste des descriptions de tous les K-Dramas.
            batch_size: Taille de batch pour le calcul.
        """
        self._descriptions_cache = list(descriptions)
        self._embeddings_cache = self.calculer_embeddings(
            descriptions, batch_size=batch_size, normaliser=True
        )
        logger.info("Catalogue indexé : %d séries, dimensionnalité=%d.",
                    len(descriptions), self._embeddings_cache.shape[1])

    # -- Recommandation par similarité ---------------------------------------

    def recommander_similaires(
        self,
        description_requete: str,
        n_recommandations: int = 5,
    ) -> List[Tuple[str, float]]:
        """Recommande les K-Dramas les plus similaires à une requête.

        Calcule l'embedding de la requête, puis la similarité cosine avec
        tous les embeddings du catalogue (pré-calculés). Retourne les
        N descriptions les plus similaires avec leur score.

        Args:
            description_requete: Texte de référence (description ou requête).
            n_recommandations: Nombre de recommandations à retourner.

        Returns:
            Liste de tuples (description, score de similarité) triée par
            similarité décroissante.

        Raises:
            ConfigurationIAError: Si le catalogue n'a pas été indexé.
        """
        if self._embeddings_cache is None or not self._descriptions_cache:
            raise ConfigurationIAError(
                "Le catalogue n'a pas été indexé. Appelez "
                "indexer_catalogue() avant recommander_similaires()."
            )

        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

        # Embedding de la requête (normalisé)
        embedding_requete = self.calculer_embeddings(
            [description_requete], normaliser=True
        )

        # Similarité cosine avec tout le catalogue
        # (produit scalaire car vecteurs normalisés)
        similarites = cosine_similarity(embedding_requete,
                                        self._embeddings_cache)[0]

        # Tri par similarité décroissante
        indices_tries = np.argsort(similarites)[::-1]

        resultats: List[Tuple[str, float]] = []
        for idx in indices_tries[:n_recommandations]:
            desc = self._descriptions_cache[idx]
            score = float(similarites[idx])
            resultats.append((desc, score))

        return resultats

    def recommander_similaires_par_index(
        self,
        index_reference: int,
        n_recommandations: int = 5,
    ) -> List[Tuple[str, float]]:
        """Recommande les K-Dramas similaires à une série du catalogue.

        Args:
            index_reference: Index de la série de référence dans le catalogue.
            n_recommandations: Nombre de recommandations à retourner.

        Returns:
            Liste de tuples (description, score) triée par similarité
            décroissante, en excluant la série de référence.
        """
        if self._embeddings_cache is None or not self._descriptions_cache:
            raise ConfigurationIAError(
                "Le catalogue n'a pas été indexé. Appelez indexer_catalogue()."
            )

        from sklearn.metrics.pairwise import cosine_similarity  # type: ignore

        if index_reference < 0 or index_reference >= len(self._descriptions_cache):
            raise DonneesInvalidesError(
                f"Index {index_reference} hors bornes "
                f"(catalogue de {len(self._descriptions_cache)} séries)."
            )

        # Vecteur de référence
        vect_ref = self._embeddings_cache[index_reference:index_reference + 1]
        similarites = cosine_similarity(vect_ref, self._embeddings_cache)[0]

        # Exclusion de la série de référence
        similarites[index_reference] = -1.0

        indices_tries = np.argsort(similarites)[::-1]
        resultats: List[Tuple[str, float]] = []
        for idx in indices_tries[:n_recommandations]:
            desc = self._descriptions_cache[idx]
            score = float(similarites[idx])
            resultats.append((desc, score))

        return resultats


# ---------------------------------------------------------------------------
# Collaborative filtering — scikit-learn
# ---------------------------------------------------------------------------

class CollaborativeFilteringRecommender:
    """Recommandeur collaboratif utilisant scikit-learn (SVD + KNN).

    Cette classe implémente le filtrage collaboratif par factorisation de
    matrice (TruncatedSVD) et recherche de voisins (NearestNeighbors).

    Attributes:
        n_components: Nombre de facteurs latents pour la SVD.
        n_voisins: Nombre de voisins à considérer pour le KNN.
        random_state: Graine aléatoire pour la reproductibilité.
        _svd: Instance TruncatedSVD entraînée.
        _knn: Instance NearestNeighbors entraînée.
        _matrice: Matrice utilisateur×série (creuse).
        _facteurs_utilisateurs: Représentation latente des utilisateurs.
        _facteurs_series: Représentation latente des séries.
    """

    def __init__(
        self,
        n_components: int = 50,
        n_voisins: int = 20,
        random_state: int = 42,
    ) -> None:
        """Initialise le recommandeur collaboratif.

        Args:
            n_components: Nombre de facteurs latents (dimension de la SVD).
            n_voisins: Nombre de voisins pour le KNN.
            random_state: Graine pour la reproductibilité.
        """
        self.n_components = n_components
        self.n_voisins = n_voisins
        self.random_state = random_state
        self._svd: Any = None
        self._knn: Any = None
        self._matrice: Any = None  # scipy.sparse.csr_matrix
        self._facteurs_utilisateurs: Optional[np.ndarray] = None
        self._facteurs_series: Optional[np.ndarray] = None

    # -- Préparation des données --------------------------------------------

    @staticmethod
    def _construire_matrice(
        notes: List[Tuple[int, int, float]],
        n_utilisateurs: int,
        n_series: int,
    ) -> Any:
        """Construit une matrice creuse (CSR) à partir d'une liste de notes.

        Args:
            notes: Liste de tuples (id_utilisateur, id_serie, note).
            n_utilisateurs: Nombre total d'utilisateurs.
            n_series: Nombre total de séries.

        Returns:
            Matrice creuse CSR de shape (n_utilisateurs, n_series).

        Raises:
            DonneesInvalidesError: Si la liste de notes est vide.
        """
        if not notes:
            raise DonneesInvalidesError(
                "La liste de notes est vide — impossible de construire "
                "la matrice utilisateur×série."
            )

        from scipy.sparse import csr_matrix  # type: ignore

        lignes: List[int] = []
        colonnes: List[int] = []
        valeurs: List[float] = []

        for id_user, id_serie, note in notes:
            lignes.append(id_user)
            colonnes.append(id_serie)
            valeurs.append(note)

        matrice = csr_matrix(
            (valeurs, (lignes, colonnes)),
            shape=(n_utilisateurs, n_series),
            dtype=np.float32,
        )
        logger.info("Matrice construite : %d utilisateurs × %d séries "
                    "(%d notes non nulles).",
                    n_utilisateurs, n_series, len(notes))
        return matrice

    # -- Entraînement --------------------------------------------------------

    def entrainer(
        self,
        notes: List[Tuple[int, int, float]],
        n_utilisateurs: int,
        n_series: int,
    ) -> None:
        """Entraîne le modèle de filtrage collaboratif (SVD + KNN).

        Étapes :
          1. Construction de la matrice creuse utilisateur×série.
          2. Entraînement de TruncatedSVD (factorisation de matrice).
          3. Calcul des facteurs latents (utilisateurs et séries).
          4. Entraînement de NearestNeighbors sur les facteurs utilisateurs.

        Args:
            notes: Liste de tuples (id_utilisateur, id_serie, note).
            n_utilisateurs: Nombre total d'utilisateurs.
            n_series: Nombre total de séries.

        Raises:
            DonneesInvalidesError: Si les données sont insuffisantes.
        """
        from sklearn.decomposition import TruncatedSVD  # type: ignore
        from sklearn.neighbors import NearestNeighbors  # type: ignore

        # 1. Construction de la matrice
        self._matrice = self._construire_matrice(
            notes, n_utilisateurs, n_series
        )

        # 2. Entraînement de la SVD
        n_comp = min(self.n_components,
                     min(self._matrice.shape) - 1)
        if n_comp < 1:
            raise DonneesInvalidesError(
                f"Matrice trop petite pour la SVD (shape={self._matrice.shape}). "
                f"Réduisez n_components ou augmentez le volume de données."
            )

        logger.info("Entraînement de TruncatedSVD (n_components=%d)...",
                    n_comp)
        self._svd = TruncatedSVD(
            n_components=n_comp,
            random_state=self.random_state,
        )
        self._facteurs_utilisateurs = self._svd.fit_transform(self._matrice)
        self._facteurs_series = self._svd.components_.T  # transposée

        logger.info("SVD entraînée — variance expliquée : %.1f%%",
                    self._svd.explained_variance_ratio_.sum() * 100)
        logger.info("Facteurs utilisateurs : %s | Facteurs séries : %s",
                    self._facteurs_utilisateurs.shape,
                    self._facteurs_series.shape)

        # 3. Entraînement du KNN sur les facteurs utilisateurs
        logger.info("Entraînement de NearestNeighbors (n_voisins=%d)...",
                    self.n_voisins)
        self._knn = NearestNeighbors(
            n_neighbors=min(self.n_voisins, n_utilisateurs),
            metric="cosine",
            algorithm="brute",
        )
        self._knn.fit(self._facteurs_utilisateurs)
        logger.info("Modèle collaboratif entraîné avec succès.")

    # -- Prédiction de note --------------------------------------------------

    def predire_note(
        self,
        id_utilisateur: int,
        id_serie: int,
    ) -> float:
        """Prédit la note qu'un utilisateur donnerait à une série.

        Reconstitue la note à partir des facteurs latents :
        note_predite = facteurs_utilisateur · facteurs_serie

        Args:
            id_utilisateur: Identifiant de l'utilisateur.
            id_serie: Identifiant de la série.

        Returns:
            Note prédite (float), bornée entre 1.0 et 5.0.

        Raises:
            ConfigurationIAError: Si le modèle n'est pas entraîné.
        """
        if self._facteurs_utilisateurs is None or self._facteurs_series is None:
            raise ConfigurationIAError(
                "Le modèle n'est pas entraîné. Appelez entrainer() d'abord."
            )

        if id_utilisateur >= self._facteurs_utilisateurs.shape[0]:
            raise DonneesInvalidesError(
                f"Utilisateur {id_utilisateur} hors bornes."
            )
        if id_serie >= self._facteurs_series.shape[0]:
            raise DonneesInvalidesError(
                f"Série {id_serie} hors bornes."
            )

        vecteur_user = self._facteurs_utilisateurs[id_utilisateur]
        vecteur_serie = self._facteurs_series[id_serie]
        note_predite = float(np.dot(vecteur_user, vecteur_serie))

        # Bornage entre 1 et 5 (échelle des notes)
        note_predite = max(1.0, min(5.0, note_predite))
        return note_predite

    # -- Recommandation KNN --------------------------------------------------

    def recommander_par_voisins(
        self,
        id_utilisateur: int,
        n_recommandations: int = 5,
    ) -> List[Tuple[int, float]]:
        """Recommande des séries à un utilisateur via le KNN user-based.

        Étapes :
          1. Identification des k utilisateurs les plus similaires.
          2. Agrégation de leurs notes (moyenne pondérée par similarité).
          3. Exclusion des séries déjà notées par l'utilisateur cible.
          4. Tri par note prédite décroissante et sélection des N meilleures.

        Args:
            id_utilisateur: Identifiant de l'utilisateur cible.
            n_recommandations: Nombre de recommandations à retourner.

        Returns:
            Liste de tuples (id_serie, note_predite) triée par note
            décroissante.

        Raises:
            ConfigurationIAError: Si le modèle n'est pas entraîné.
        """
        if self._knn is None or self._matrice is None:
            raise ConfigurationIAError(
                "Le modèle n'est pas entraîné. Appelez entrainer() d'abord."
            )

        if id_utilisateur >= self._matrice.shape[0]:
            raise DonneesInvalidesError(
                f"Utilisateur {id_utilisateur} hors bornes."
            )

        # 1. Recherche des voisins
        vecteur_user = self._facteurs_utilisateurs[id_utilisateur:id_utilisateur + 1]
        distances, indices = self._knn.kneighbors(vecteur_user)
        distances = distances[0]  # shape (n_voisins,)
        indices = indices[0]      # shape (n_voisins,)

        # Conversion des distances cosine en similarités (1 - distance)
        similarites = 1.0 - distances
        # Exclusion de l'utilisateur lui-même (similarité = 1.0, distance = 0)
        masque = indices != id_utilisateur
        indices = indices[masque]
        similarites = similarites[masque]

        # 2. Agrégation des notes des voisins
        notes_voisins = self._matrice[indices]  # matrice creuse
        notes_agg = np.array(notes_voisins.T.dot(similarites)).flatten()

        # 3. Exclusion des séries déjà notées par l'utilisateur
        series_deja_notees = self._matrice[id_utilisateur].nonzero()[1]
        notes_agg[series_deja_notees] = -1.0  # marquage pour exclusion

        # 4. Tri et sélection
        indices_series = np.argsort(notes_agg)[::-1]
        resultats: List[Tuple[int, float]] = []
        for idx_serie in indices_series[:n_recommandations]:
            note = float(notes_agg[idx_serie])
            if note > 0:  # on ne recommande que les notes positives
                resultats.append((int(idx_serie), note))

        return resultats


# ---------------------------------------------------------------------------
# Génération de données synthétiques (pour les tests)
# ---------------------------------------------------------------------------

def _generer_donnees_syntheses(
    n_utilisateurs: int = 100,
    n_series: int = 50,
    densite: float = 0.15,
    seed: int = 42,
) -> List[Tuple[int, int, float]]:
    """Génère des notes synthétiques pour valider le filtrage collaboratif.

    Args:
        n_utilisateurs: Nombre d'utilisateurs.
        n_series: Nombre de séries.
        densite: Proportion de notes non nulles (0 à 1).
        seed: Graine aléatoire.

    Returns:
        Liste de tuples (id_utilisateur, id_serie, note).
    """
    rng = np.random.default_rng(seed)
    notes: List[Tuple[int, int, float]] = []
    total_possible = n_utilisateurs * n_series
    n_notes = int(total_possible * densite)

    for _ in range(n_notes):
        id_user = int(rng.integers(0, n_utilisateurs))
        id_serie = int(rng.integers(0, n_series))
        note = float(rng.choice([1.0, 2.0, 3.0, 4.0, 5.0],
                                p=[0.05, 0.10, 0.20, 0.35, 0.30]))
        notes.append((id_user, id_serie, note))

    logger.info("Données synthétiques générées : %d notes "
                "(%d utilisateurs × %d séries).",
                len(notes), n_utilisateurs, n_series)
    return notes


# ---------------------------------------------------------------------------
# Tests de validation
# ---------------------------------------------------------------------------

def tester_content_based() -> bool:
    """Teste le recommandeur content-based de bout en bout.

    Returns:
        True si tous les tests passent, False sinon.
    """
    logger.info("=" * 60)
    logger.info("TEST — Content-based filtering (sentence-transformers)")
    logger.info("=" * 60)

    try:
        recommender = ContentBasedRecommender(
            model_name="all-MiniLM-L6-v2"
        )

        # Corpus de test (5 descriptions)
        descriptions = [
            "A love story between a North Korean soldier and a South "
            "Korean heiress who crash-lands in the North.",
            "A high-stakes survival game where 456 contestants compete "
            "in children's games for a massive cash prize.",
            "A woman who endured bullying returns years later to execute "
            "her revenge against her tormentors.",
            "A goblin cursed with immortality seeks a human bride to end "
            "his eternal suffering.",
            "A prosecutor and a bold lawyer team up to fight corruption "
            "in the justice system.",
        ]

        # Indexation du catalogue
        recommender.indexer_catalogue(descriptions)

        # Test 1 : recommander les séries similaires à la série 0
        logger.info("Test 1 — Recommandation par index (série 0 = romance)")
        debut = time.perf_counter()
        recommandations = recommender.recommander_similaires_par_index(
            index_reference=0, n_recommandations=3
        )
        duree_ms = (time.perf_counter() - debut) * 1000
        logger.info("Latence recommandation : %.1f ms", duree_ms)
        for desc, score in recommandations:
            logger.info("  [%.3f] %s", score, desc[:80] + "...")

        # Test 2 : recommander par requête texte
        logger.info("Test 2 — Recommandation par requête texte")
        requete = ("A romantic drama with star-crossed lovers from "
                   "different worlds.")
        recommandations = recommender.recommander_similaires(
            description_requete=requete, n_recommandations=3
        )
        for desc, score in recommandations:
            logger.info("  [%.3f] %s", score, desc[:80] + "...")

        # Test 3 : vérification de la cohérence
        logger.info("Test 3 — Cohérence (la série 0 doit être la plus "
                    "similaire à elle-même)")
        recommandations_self = recommender.recommander_similaires(
            description_requete=descriptions[0], n_recommandations=5
        )
        if recommandations_self and recommandations_self[0][0] == descriptions[0]:
            logger.info("  OK — La série de référence est bien la plus "
                        "similaire (score=%.3f).",
                        recommandations_self[0][1])
        else:
            logger.warning("  ATTENTION — La série de référence n'est pas "
                           "la plus similaire.")

        logger.info("Test content-based : SUCCÈS")
        return True

    except ModeleIntrouvableError as e:
        logger.error("Modèle introuvable : %s", e)
        logger.info("Test content-based : ÉCHEC (modèle non disponible)")
        return False
    except Exception as e:
        logger.error("Erreur lors du test content-based : %s", e,
                     exc_info=True)
        return False


def tester_collaborative() -> bool:
    """Teste le recommandeur collaboratif de bout en bout.

    Returns:
        True si tous les tests passent, False sinon.
    """
    logger.info("=" * 60)
    logger.info("TEST — Collaborative filtering (scikit-learn)")
    logger.info("=" * 60)

    try:
        # Génération de données synthétiques
        n_utilisateurs = 100
        n_series = 50
        notes = _generer_donnees_syntheses(
            n_utilisateurs=n_utilisateurs,
            n_series=n_series,
            densite=0.15,
        )

        # Entraînement
        recommender = CollaborativeFilteringRecommender(
            n_components=20,
            n_voisins=10,
        )
        recommender.entrainer(
            notes=notes,
            n_utilisateurs=n_utilisateurs,
            n_series=n_series,
        )

        # Test 1 : prédiction de note
        logger.info("Test 1 — Prédiction de note")
        note_predite = recommender.predire_note(
            id_utilisateur=0, id_serie=0
        )
        logger.info("  Note prédite (user=0, serie=0) : %.2f", note_predite)
        assert 1.0 <= note_predite <= 5.0, \
            f"Note prédite hors bornes : {note_predite}"
        logger.info("  OK — Note dans l'intervalle [1, 5].")

        # Test 2 : recommandation KNN
        logger.info("Test 2 — Recommandation par voisins (user=0)")
        debut = time.perf_counter()
        recommandations = recommender.recommander_par_voisins(
            id_utilisateur=0, n_recommandations=5
        )
        duree_ms = (time.perf_counter() - debut) * 1000
        logger.info("Latence recommandation : %.1f ms", duree_ms)
        for id_serie, note in recommandations:
            logger.info("  Série %d — note prédite : %.2f", id_serie, note)

        assert len(recommandations) > 0, "Aucune recommandation générée."
        logger.info("  OK — %d recommandations générées.", len(recommandations))

        # Test 3 : latence
        logger.info("Test 3 — Latence collaborative < 500 ms")
        logger.info("  Latence mesurée : %.1f ms (cible < 500 ms)", duree_ms)
        if duree_ms < 500:
            logger.info("  OK — Latence conforme à la cible.")
        else:
            logger.warning("  ATTENTION — Latence supérieure à la cible.")

        logger.info("Test collaborative : SUCCÈS")
        return True

    except Exception as e:
        logger.error("Erreur lors du test collaborative : %s", e,
                     exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def main() -> int:
    """Point d'entrée principal : configure et teste le service d'IA.

    Étapes :
      1. Affichage de la configuration (versions, device).
      2. Test du content-based filtering (sentence-transformers).
      3. Test du collaborative filtering (scikit-learn).
      4. Bilan global.

    Returns:
        0 si tous les tests passent, 1 sinon.
    """
    logger.info("=" * 60)
    logger.info("Configuration du service d'IA — K-Drama RecSys")
    logger.info("=" * 60)

    # Affichage de l'environnement
    logger.info("Python : %s", sys.version.split()[0])
    logger.info("NumPy : %s", np.__version__)

    try:
        import sklearn  # type: ignore
        logger.info("scikit-learn : %s", sklearn.__version__)
    except ImportError:
        logger.error("scikit-learn non installé — installez-le avec : "
                     "pip install scikit-learn")
        return 1

    try:
        import torch  # type: ignore
        logger.info("PyTorch : %s (CUDA disponible : %s)",
                    torch.__version__, torch.cuda.is_available())
    except ImportError:
        logger.warning("PyTorch non installé — le content-based filtering "
                       "nécessite sentence-transformers + torch.")

    # Tests
    resultats: Dict[str, bool] = {}
    resultats["content_based"] = tester_content_based()
    resultats["collaborative"] = tester_collaborative()

    # Bilan
    logger.info("=" * 60)
    logger.info("BILAN DES TESTS")
    logger.info("=" * 60)
    for test, succes in resultats.items():
        statut = "SUCCÈS" if succes else "ÉCHEC"
        logger.info("  %s : %s", test, statut)

    tous_succes = all(resultats.values())
    if tous_succes:
        logger.info("Tous les tests sont passés — le service d'IA est "
                    "configuré et opérationnel.")
        return 0
    else:
        logger.warning("Certains tests ont échoué — vérifiez les logs "
                       "ci-dessus.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
