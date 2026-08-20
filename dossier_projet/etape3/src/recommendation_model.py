# ============================================================
# Modèle de recommandation hybride pour K-Dramas
# Fichier : recommendation_model.py
#
# Combine :
#   1. Filtrage basé sur le contenu (content-based) via
#      sentence-transformers (embeddings sémantiques des synopsis).
#   2. Filtrage collaboratif (collaborative filtering) via
#      scikit-learn (NearestNeighbors sur matrice utilisateur-drama).
#
# Auteur : Équipe Data Science
# Étape 3 — RNCP AI Project
# ============================================================

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

logger = logging.getLogger(__name__)

# Constantes de configuration
DEFAULT_MODEL_DIR = Path(__file__).parent / "model_artifacts"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_DEFAULT = 10
RANDOM_STATE = 42


# ============================================================
# Structures de données
# ============================================================

@dataclass
class RecommendationResult:
    """Représente le résultat d'une recommandation pour un K-Drama."""

    drama_id: int
    title: str
    score: float
    genres: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convertit le résultat en dictionnaire sérialisable JSON."""
        return {
            "drama_id": self.drama_id,
            "title": self.title,
            "score": round(float(self.score), 4),
            "genres": self.genres,
            "reason": self.reason,
        }


@dataclass
class ModelMetrics:
    """Métriques d'évaluation du modèle (pour le monitoring)."""

    training_time_seconds: float = 0.0
    num_dramas: int = 0
    num_users: int = 0
    num_interactions: int = 0
    embedding_dim: int = 0
    last_trained_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "training_time_seconds": round(self.training_time_seconds, 2),
            "num_dramas": self.num_dramas,
            "num_users": self.num_users,
            "num_interactions": self.num_interactions,
            "embedding_dim": self.embedding_dim,
            "last_trained_at": self.last_trained_at,
        }


# ============================================================
# Modèle de recommandation hybride
# ============================================================

class HybridRecommender:
    """
    Modèle de recommandation hybride pour K-Dramas.

    Combine deux approches :
      - **Content-based** : utilise sentence-transformers pour générer des
        embeddings sémantiques des synopsis, puis calcule la similarité
        cosinus entre les dramas.
      - **Collaborative filtering** : utilise scikit-learn NearestNeighbors
        sur la matrice d'interactions utilisateur-drama pour identifier
        les dramas appréciés par des utilisateurs similaires.

    Le score final est une moyenne pondérée des deux approches :
        score = alpha * content_score + (1 - alpha) * collaborative_score

    Attributes:
        alpha: Poids du content-based (0.0 à 1.0).
        embedding_model_name: Nom du modèle sentence-transformers utilisé.
        content_embeddings: Matrice des embeddings de contenu (numpy array).
        collaborative_model: Modèle NearestNeighbors entraîné.
        dramas_df: DataFrame contenant les métadonnées des dramas.
        interactions_df: DataFrame des interactions utilisateur-drama.
    """

    def __init__(
        self,
        alpha: float = 0.6,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        """
        Initialise le modèle de recommandation hybride.

        Args:
            alpha: Poids du content-based filtering (entre 0 et 1).
                   Valeur par défaut 0.6 (60% content, 40% collaborative).
            embedding_model_name: Nom du modèle HuggingFace à utiliser
                                  pour les embeddings de texte.
        """
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(
                f"alpha doit être entre 0 et 1, reçu : {alpha}"
            )

        self.alpha = alpha
        self.embedding_model_name = embedding_model_name
        self.content_embeddings: np.ndarray | None = None
        self.collaborative_model: NearestNeighbors | None = None
        self.dramas_df: pd.DataFrame | None = None
        self.interactions_df: pd.DataFrame | None = None
        self.user_item_matrix: pd.DataFrame | None = None
        self._embedding_model = None
        self._is_trained = False
        self.metrics = ModelMetrics()

    # ============================================================
    # Entraînement
    # ============================================================

    def train(
        self,
        dramas_df: pd.DataFrame,
        interactions_df: pd.DataFrame,
    ) -> ModelMetrics:
        """
        Entraîne le modèle de recommandation hybride.

        Étapes :
          1. Validation des données d'entrée.
          2. Génération des embeddings de contenu (sentence-transformers).
          3. Construction de la matrice utilisateur-drama.
          4. Entraînement du modèle de filtrage collaboratif (NearestNeighbors).
          5. Calcul des métriques d'entraînement.

        Args:
            dramas_df: DataFrame avec colonnes obligatoires :
                       ['drama_id', 'title', 'synopsis', 'genres']
            interactions_df: DataFrame avec colonnes obligatoires :
                             ['user_id', 'drama_id', 'rating']

        Returns:
            ModelMetrics: Métriques d'entraînement.

        Raises:
            ValueError: Si les données d'entrée sont invalides.
        """
        start_time = time.time()
        logger.info("Début de l'entraînement du modèle hybride...")

        # --- Validation des données ---
        self._validate_training_data(dramas_df, interactions_df)
        self.dramas_df = dramas_df.copy()
        self.interactions_df = interactions_df.copy()

        # --- 1. Content-based : embeddings de contenu ---
        logger.info(
            "Génération des embeddings de contenu avec %s...",
            self.embedding_model_name,
        )
        self._load_embedding_model()
        self._generate_content_embeddings()

        # --- 2. Collaborative filtering : matrice utilisateur-drama ---
        logger.info("Construction de la matrice utilisateur-drama...")
        self._build_user_item_matrix()

        # --- 3. Entraînement du modèle collaboratif ---
        logger.info("Entraînement du modèle NearestNeighbors...")
        self._train_collaborative_model()

        # --- Calcul des métriques ---
        self.metrics.training_time_seconds = time.time() - start_time
        self.metrics.num_dramas = len(dramas_df)
        self.metrics.num_users = interactions_df["user_id"].nunique()
        self.metrics.num_interactions = len(interactions_df)
        self.metrics.embedding_dim = (
            self.content_embeddings.shape[1]
            if self.content_embeddings is not None
            else 0
        )
        self.metrics.last_trained_at = pd.Timestamp.now().isoformat()

        self._is_trained = True
        logger.info(
            "Entraînement terminé en %.2f secondes. "
            "%d dramas, %d utilisateurs, %d interactions.",
            self.metrics.training_time_seconds,
            self.metrics.num_dramas,
            self.metrics.num_users,
            self.metrics.num_interactions,
        )
        return self.metrics

    def _validate_training_data(
        self,
        dramas_df: pd.DataFrame,
        interactions_df: pd.DataFrame,
    ) -> None:
        """Valide les DataFrames d'entraînement avant utilisation."""
        required_drama_cols = {"drama_id", "title", "synopsis", "genres"}
        required_interaction_cols = {"user_id", "drama_id", "rating"}

        if dramas_df.empty:
            raise ValueError("Le DataFrame des dramas est vide.")
        if interactions_df.empty:
            raise ValueError("Le DataFrame des interactions est vide.")

        missing_drama = required_drama_cols - set(dramas_df.columns)
        if missing_drama:
            raise ValueError(
                f"Colonnes manquantes dans dramas_df : {missing_drama}"
            )

        missing_interaction = required_interaction_cols - set(
            interactions_df.columns
        )
        if missing_interaction:
            raise ValueError(
                f"Colonnes manquantes dans interactions_df : "
                f"{missing_interaction}"
            )

        # Vérification des types de rating
        if not pd.api.types.is_numeric_dtype(interactions_df["rating"]):
            raise ValueError("La colonne 'rating' doit être numérique.")

        logger.info("Validation des données d'entraînement : OK")

    def _load_embedding_model(self) -> None:
        """Charge le modèle sentence-transformers (lazy loading)."""
        if self._embedding_model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(
                self.embedding_model_name
            )
            logger.info(
                "Modèle sentence-transformers chargé : %s",
                self.embedding_model_name,
            )
        except ImportError:
            logger.warning(
                "sentence-transformers non disponible. "
                "Utilisation d'un fallback TF-IDF."
            )
            self._embedding_model = _TFIDFFallback()

    def _generate_content_embeddings(self) -> None:
        """
        Génère les embeddings de contenu pour chaque K-Drama.

        Combine le synopsis et les genres dans un texte unique,
        puis génère l'embedding via sentence-transformers.
        """
        if self.dramas_df is None:
            raise RuntimeError("dramas_df n'est pas initialisé.")

        # Construction du texte combiné : synopsis + genres
        texts = []
        for _, row in self.dramas_df.iterrows():
            synopsis = str(row.get("synopsis", ""))
            genres = str(row.get("genres", ""))
            combined = f"{synopsis} Genres: {genres}"
            texts.append(combined)

        # Génération des embeddings
        embeddings = self._embedding_model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        # Normalisation L2 pour la similarité cosinus
        self.content_embeddings = normalize(embeddings, norm="l2")
        logger.info(
            "Embeddings générés : forme %s",
            self.content_embeddings.shape,
        )

    def _build_user_item_matrix(self) -> None:
        """Construit la matrice d'interactions utilisateur-drama."""
        if self.interactions_df is None:
            raise RuntimeError("interactions_df n'est pas initialisé.")

        # Pivot : lignes = utilisateurs, colonnes = dramas, valeurs = rating
        self.user_item_matrix = self.interactions_df.pivot_table(
            index="user_id",
            columns="drama_id",
            values="rating",
            fill_value=0.0,
        )
        logger.info(
            "Matrice utilisateur-drama : %d utilisateurs x %d dramas",
            self.user_item_matrix.shape[0],
            self.user_item_matrix.shape[1],
        )

    def _train_collaborative_model(self) -> None:
        """Entraîne le modèle NearestNeighbors pour le filtrage collaboratif."""
        if self.user_item_matrix is None:
            raise RuntimeError("user_item_matrix n'est pas construit.")

        # Utilisation de la métrique cosine pour la similarité entre utilisateurs
        self.collaborative_model = NearestNeighbors(
            n_neighbors=min(
                20, self.user_item_matrix.shape[0]
            ),
            metric="cosine",
            algorithm="brute",
        )
        self.collaborative_model.fit(self.user_item_matrix.values)
        logger.info("Modèle NearestNeighbors entraîné avec succès.")

    # ============================================================
    # Inférence
    # ============================================================

    def recommend(
        self,
        user_id: int | None = None,
        drama_id: int | None = None,
        top_k: int = TOP_K_DEFAULT,
    ) -> list[RecommendationResult]:
        """
        Génère des recommandations pour un utilisateur ou un drama donné.

        Deux modes de fonctionnement :
          - **Mode utilisateur** (user_id fourni) : recommande des dramas
            basés sur l'historique de l'utilisateur et les utilisateurs similaires.
          - **Mode item** (drama_id fourni) : recommande des dramas similaires
            au drama spécifié (content-based + collaborative).

        Args:
            user_id: ID de l'utilisateur pour les recommandations personnalisées.
            drama_id: ID du drama de référence pour les recommandations similaires.
            top_k: Nombre de recommandations à retourner (défaut : 10).

        Returns:
            Liste triée de RecommendationResult (du plus pertinent au moins pertinent).

        Raises:
            RuntimeError: Si le modèle n'est pas entraîné.
            ValueError: Si ni user_id ni drama_id n'est fourni, ou si top_k <= 0.
        """
        self._check_trained()

        if top_k <= 0:
            raise ValueError(f"top_k doit être > 0, reçu : {top_k}")

        if user_id is None and drama_id is None:
            raise ValueError(
                "Au moins un de user_id ou drama_id doit être fourni."
            )

        if user_id is not None:
            return self._recommend_for_user(user_id, top_k)
        else:
            assert drama_id is not None
            return self._recommend_similar_to_drama(drama_id, top_k)

    def predict(
        self,
        user_id: int,
        drama_id: int,
    ) -> float:
        """
        Prédit la note qu'un utilisateur donnerait à un K-Drama.

        Utilise une combinaison pondérée :
          - Score de similarité de contenu entre le drama cible et
            les dramas déjà notés par l'utilisateur.
          - Score collaboratif basé sur les utilisateurs similaires
            qui ont noté ce drama.

        Args:
            user_id: ID de l'utilisateur.
            drama_id: ID du drama à évaluer.

        Returns:
            Score prédit entre 0.0 et 10.0.

        Raises:
            RuntimeError: Si le modèle n'est pas entraîné.
            ValueError: Si l'utilisateur ou le drama n'existe pas.
        """
        self._check_trained()

        if self.dramas_df is None or self.user_item_matrix is None:
            raise RuntimeError("Modèle incomplet.")

        if drama_id not in self.dramas_df["drama_id"].values:
            raise ValueError(f"Drama {drama_id} introuvable dans le catalogue.")

        # Score content-based
        content_score = self._compute_content_prediction(user_id, drama_id)

        # Score collaboratif
        collab_score = self._compute_collaborative_prediction(user_id, drama_id)

        # Combinaison pondérée
        predicted = self.alpha * content_score + (1 - self.alpha) * collab_score

        # Bornage entre 0 et 10
        return float(np.clip(predicted, 0.0, 10.0))

    def _recommend_for_user(
        self,
        user_id: int,
        top_k: int,
    ) -> list[RecommendationResult]:
        """
        Génère des recommandations personnalisées pour un utilisateur.

        Étapes :
          1. Identifier les utilisateurs similaires (NearestNeighbors).
          2. Agréger les notes des utilisateurs similaires pour les dramas
             non encore vus par l'utilisateur cible.
          3. Compléter avec le score content-based basé sur les dramas
             appréciés par l'utilisateur.
          4. Combiner les scores et retourner le top_k.

        Args:
            user_id: ID de l'utilisateur.
            top_k: Nombre de recommandations.

        Returns:
            Liste de RecommendationResult.
        """
        if self.user_item_matrix is None or self.collaborative_model is None:
            raise RuntimeError("Modèle collaboratif non entraîné.")

        # Vérification de l'existence de l'utilisateur
        if user_id not in self.user_item_matrix.index:
            # Utilisateur froid : fallback content-based sur les dramas populaires
            logger.info(
                "Utilisateur %d inconnu. Fallback sur les dramas populaires.",
                user_id,
            )
            return self._recommend_popular(top_k)

        # --- Étape 1 : Utilisateurs similaires ---
        user_vector = self.user_item_matrix.loc[user_id].values.reshape(1, -1)
        distances, indices = self.collaborative_model.kneighbors(user_vector)
        similar_users = self.user_item_matrix.index[indices[0]]

        # --- Étape 2 : Agrégation des notes des utilisateurs similaires ---
        similar_ratings = self.user_item_matrix.loc[similar_users]
        # Exclure les dramas déjà vus par l'utilisateur
        seen_dramas = self.user_item_matrix.loc[user_id]
        unseen_mask = seen_dramas == 0.0
        collab_scores = similar_ratings.mean(axis=0)
        collab_scores = collab_scores[unseen_mask]

        # --- Étape 3 : Score content-based ---
        # Basé sur les dramas les mieux notés par l'utilisateur
        top_rated = seen_dramas[seen_dramas > 0].sort_values(ascending=False)
        content_scores = pd.Series(0.0, index=collab_scores.index)

        if len(top_rated) > 0 and self.content_embeddings is not None:
            drama_ids = self.dramas_df["drama_id"].tolist()
            for drama_id_val, rating in top_rated.head(5).items():
                if drama_id_val in drama_ids:
                    idx = drama_ids.index(drama_id_val)
                    sims = self.content_embeddings @ self.content_embeddings[idx]
                    for did in content_scores.index:
                        if did in drama_ids:
                            didx = drama_ids.index(did)
                            content_scores[did] += sims[didx] * rating

        # Normalisation
        if content_scores.max() > 0:
            content_scores = content_scores / content_scores.max() * 10

        # --- Étape 4 : Combinaison ---
        final_scores = (
            self.alpha * content_scores + (1 - self.alpha) * collab_scores
        )
        final_scores = final_scores.sort_values(ascending=False).head(top_k)

        results: list[RecommendationResult] = []
        for did, score in final_scores.items():
            drama_info = self._get_drama_info(int(did))
            if drama_info:
                results.append(
                    RecommendationResult(
                        drama_id=int(did),
                        title=drama_info["title"],
                        score=float(score),
                        genres=drama_info["genres"],
                        reason="Recommended based on your history "
                        "and similar users.",
                    )
                )

        return results

    def _recommend_similar_to_drama(
        self,
        drama_id: int,
        top_k: int,
    ) -> list[RecommendationResult]:
        """
        Recommande des dramas similaires à un drama donné.

        Combine la similarité de contenu (embeddings) et la co-occurrence
        dans les interactions des utilisateurs.

        Args:
            drama_id: ID du drama de référence.
            top_k: Nombre de recommandations.

        Returns:
            Liste de RecommendationResult.
        """
        if self.dramas_df is None or self.content_embeddings is None:
            raise RuntimeError("Modèle de contenu non entraîné.")

        drama_ids = self.dramas_df["drama_id"].tolist()
        if drama_id not in drama_ids:
            raise ValueError(f"Drama {drama_id} introuvable dans le catalogue.")

        idx = drama_ids.index(drama_id)

        # --- Score content-based : similarité cosinus ---
        content_sims = self.content_embeddings @ self.content_embeddings[idx]
        content_scores = pd.Series(
            content_sims, index=drama_ids
        )
        # Exclure le drama lui-même
        content_scores = content_scores.drop(drama_id, errors="ignore")

        # --- Score collaboratif : co-occurrence ---
        collab_scores = pd.Series(0.0, index=drama_ids)
        if self.interactions_df is not None:
            users_who_watched = self.interactions_df[
                self.interactions_df["drama_id"] == drama_id
            ]["user_id"].unique()
            for uid in users_who_watched:
                other_dramas = self.interactions_df[
                    (self.interactions_df["user_id"] == uid)
                    & (self.interactions_df["drama_id"] != drama_id)
                ]
                for _, row in other_dramas.iterrows():
                    did_val = int(row["drama_id"])
                    if did_val in collab_scores.index:
                        collab_scores[did_val] += row["rating"]

        # Normalisation du score collaboratif
        if collab_scores.max() > 0:
            collab_scores = collab_scores / collab_scores.max() * 10

        # --- Combinaison ---
        final_scores = (
            self.alpha * content_scores * 10
            + (1 - self.alpha) * collab_scores
        )
        final_scores = final_scores.sort_values(ascending=False).head(top_k)

        results: list[RecommendationResult] = []
        for did, score in final_scores.items():
            if score <= 0:
                continue
            drama_info = self._get_drama_info(int(did))
            if drama_info:
                results.append(
                    RecommendationResult(
                        drama_id=int(did),
                        title=drama_info["title"],
                        score=float(score),
                        genres=drama_info["genres"],
                        reason="Similar to the selected drama "
                        "(content and user preferences).",
                    )
                )

        return results

    def _recommend_popular(self, top_k: int) -> list[RecommendationResult]:
        """
        Fallback pour les utilisateurs froids : recommande les dramas
        les plus populaires (note moyenne la plus élevée).

        Args:
            top_k: Nombre de recommandations.

        Returns:
            Liste de RecommendationResult.
        """
        if self.interactions_df is None or self.dramas_df is None:
            return []

        popular = (
            self.interactions_df.groupby("drama_id")["rating"]
            .mean()
            .sort_values(ascending=False)
            .head(top_k)
        )

        results: list[RecommendationResult] = []
        for did, score in popular.items():
            drama_info = self._get_drama_info(int(did))
            if drama_info:
                results.append(
                    RecommendationResult(
                        drama_id=int(did),
                        title=drama_info["title"],
                        score=float(score),
                        genres=drama_info["genres"],
                        reason="Popular drama (high average rating).",
                    )
                )

        return results

    def _compute_content_prediction(
        self, user_id: int, drama_id: int
    ) -> float:
        """
        Calcule le score prédit basé sur le contenu pour un couple
        utilisateur-drama.

        Args:
            user_id: ID de l'utilisateur.
            drama_id: ID du drama.

        Returns:
            Score entre 0 et 10.
        """
        if self.user_item_matrix is None or self.content_embeddings is None:
            return 5.0  # Score neutre si pas de données

        if user_id not in self.user_item_matrix.index:
            return 5.0

        user_ratings = self.user_item_matrix.loc[user_id]
        rated_dramas = user_ratings[user_ratings > 0]

        if len(rated_dramas) == 0:
            return 5.0

        drama_ids = self.dramas_df["drama_id"].tolist()
        if drama_id not in drama_ids:
            return 5.0

        target_idx = drama_ids.index(drama_id)
        target_emb = self.content_embeddings[target_idx]

        weighted_sum = 0.0
        weight_total = 0.0
        for did, rating in rated_dramas.items():
            if did in drama_ids:
                didx = drama_ids.index(did)
                sim = float(
                    np.dot(target_emb, self.content_embeddings[didx])
                )
                weighted_sum += sim * rating
                weight_total += abs(sim)

        if weight_total == 0:
            return 5.0

        return float(np.clip(weighted_sum / weight_total, 0.0, 10.0))

    def _compute_collaborative_prediction(
        self, user_id: int, drama_id: int
    ) -> float:
        """
        Calcule le score prédit basé sur le filtrage collaboratif.

        Args:
            user_id: ID de l'utilisateur.
            drama_id: ID du drama.

        Returns:
            Score entre 0 et 10.
        """
        if (
            self.user_item_matrix is None
            or self.collaborative_model is None
        ):
            return 5.0

        if user_id not in self.user_item_matrix.index:
            return 5.0

        if drama_id not in self.user_item_matrix.columns:
            return 5.0

        user_vector = self.user_item_matrix.loc[user_id].values.reshape(1, -1)
        distances, indices = self.collaborative_model.kneighbors(user_vector)
        similar_users = self.user_item_matrix.index[indices[0]]

        # Note moyenne donnée par les utilisateurs similaires pour ce drama
        ratings_from_similar = []
        for uid in similar_users:
            rating = self.user_item_matrix.loc[uid, drama_id]
            if rating > 0:
                ratings_from_similar.append(rating)

        if not ratings_from_similar:
            return 5.0

        return float(np.clip(np.mean(ratings_from_similar), 0.0, 10.0))

    # ============================================================
    # Sérialisation
    # ============================================================

    def save(self, model_dir: Path | str = DEFAULT_MODEL_DIR) -> None:
        """
        Sérialise le modèle entraîné sur disque.

        Fichiers générés :
          - model.joblib : objet HybridRecommender (sans le modèle ST).
          - content_embeddings.npy : matrice d'embeddings de contenu.
          - metrics.json : métriques d'entraînement.

        Args:
            model_dir: Répertoire de sauvegarde.
        """
        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)

        # Sauvegarde du modèle (sans le modèle sentence-transformers)
        embedding_model_cache = self._embedding_model
        self._embedding_model = None  # On ne sérialise pas le modèle ST
        joblib.dump(self, model_dir / "model.joblib", compress=3)
        self._embedding_model = embedding_model_cache

        # Sauvegarde des embeddings
        if self.content_embeddings is not None:
            np.save(
                model_dir / "content_embeddings.npy",
                self.content_embeddings,
            )

        # Sauvegarde des métriques
        with open(model_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump(self.metrics.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info("Modèle sauvegardé dans %s", model_dir)

    @classmethod
    def load(cls, model_dir: Path | str = DEFAULT_MODEL_DIR) -> "HybridRecommender":
        """
        Charge un modèle sérialisé depuis le disque.

        Args:
            model_dir: Répertoire contenant les artefacts du modèle.

        Returns:
            Instance de HybridRecommender prête pour l'inférence.

        Raises:
            FileNotFoundError: Si les fichiers du modèle sont introuvables.
        """
        model_dir = Path(model_dir)
        model_path = model_dir / "model.joblib"

        if not model_path.exists():
            raise FileNotFoundError(
                f"Fichier modèle introuvable : {model_path}"
            )

        model = joblib.load(model_path)

        # Chargement des embeddings
        emb_path = model_dir / "content_embeddings.npy"
        if emb_path.exists():
            model.content_embeddings = np.load(emb_path)

        # Rechargement du modèle sentence-transformers (lazy)
        model._embedding_model = None

        logger.info("Modèle chargé depuis %s", model_dir)
        return model

    # ============================================================
    # Utilitaires
    # ============================================================

    def _check_trained(self) -> None:
        """Vérifie que le modèle a été entraîné."""
        if not self._is_trained:
            raise RuntimeError(
                "Le modèle n'est pas entraîné. Appelez train() d'abord."
            )

    def _get_drama_info(self, drama_id: int) -> dict[str, Any] | None:
        """Récupère les métadonnées d'un drama par son ID."""
        if self.dramas_df is None:
            return None
        row = self.dramas_df[self.dramas_df["drama_id"] == drama_id]
        if row.empty:
            return None
        row = row.iloc[0]

        def _repair_text(value: str) -> str:
            """Repair common mojibake artifacts when UTF-8 was decoded as Latin-1."""
            if not value:
                return value
            try:
                return value.encode("latin1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                return value

        def _to_english_genre(label: str) -> str:
            mapping = {
                "comedie": "Comedy",
                "drame": "Drama",
                "mystere": "Mystery",
                "historique": "Historical",
                "fantastique": "Fantasy",
                "science-fiction": "Science Fiction",
                "surnaturel": "Supernatural",
                "politique": "Political",
                "juridique": "Legal",
                "famille": "Family",
                "amitie": "Friendship",
                "tranche de vie": "Slice of Life",
                "jeunesse": "Youth",
                "ecole": "School",
                "psychologique": "Psychological",
                "militaire": "Military",
                "espionnage": "Espionage",
                "voyage dans le temps": "Time Travel",
            }
            key = (
                label.strip()
                .lower()
                .replace("é", "e")
                .replace("è", "e")
                .replace("ê", "e")
                .replace("ë", "e")
                .replace("à", "a")
                .replace("â", "a")
                .replace("ä", "a")
                .replace("î", "i")
                .replace("ï", "i")
                .replace("ô", "o")
                .replace("ö", "o")
                .replace("ù", "u")
                .replace("û", "u")
                .replace("ü", "u")
                .replace("ç", "c")
            )
            return mapping.get(key, label.strip())

        genres_value = row.get("genres", "")
        parsed_genres: list[str]
        if isinstance(genres_value, list):
            parsed_genres = [str(g) for g in genres_value]
        elif isinstance(genres_value, str):
            text_value = genres_value.strip()
            if not text_value:
                parsed_genres = []
            elif text_value.startswith("[") and text_value.endswith("]"):
                try:
                    decoded = json.loads(text_value)
                    if isinstance(decoded, list):
                        parsed_genres = [str(g) for g in decoded]
                    else:
                        parsed_genres = [str(decoded)]
                except json.JSONDecodeError:
                    parsed_genres = [g.strip() for g in text_value.split(",") if g.strip()]
            else:
                parsed_genres = [g.strip() for g in text_value.split(",") if g.strip()]
        else:
            parsed_genres = [str(genres_value)] if genres_value else []

        genres: list[str] = []
        for genre in parsed_genres:
            clean = _repair_text(genre.strip().strip("[]\"'"))
            clean = _to_english_genre(clean)
            if clean and clean not in genres:
                genres.append(clean)

        title = _repair_text(str(row.get("title", "Unknown")))
        return {
            "title": title,
            "genres": genres,
        }

    def get_model_info(self) -> dict[str, Any]:
        """
        Retourne les informations sur le modèle pour le endpoint /health.

        Returns:
            Dictionnaire avec les métadonnées du modèle.
        """
        return {
            "model_type": "HybridRecommender",
            "alpha": self.alpha,
            "embedding_model": self.embedding_model_name,
            "is_trained": self._is_trained,
            "metrics": self.metrics.to_dict() if self._is_trained else None,
        }


# ============================================================
# Fallback TF-IDF (si sentence-transformers indisponible)
# ============================================================

class _TFIDFFallback:
    """
    Fallback utilisant TF-IDF (scikit-learn) si sentence-transformers
    n'est pas installé. Permet au modèle de fonctionner dans des
    environnements contraints (CI, tests unitaires).
    """

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(
            max_features=384,
            stop_words="english",
            ngram_range=(1, 2),
        )
        self._is_fitted = False

    def encode(
        self,
        texts: list[str],
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """Encode les textes en embeddings TF-IDF."""
        if not self._is_fitted:
            embeddings = self.vectorizer.fit_transform(texts).toarray()
            self._is_fitted = True
        else:
            embeddings = self.vectorizer.transform(texts).toarray()
        return embeddings.astype(np.float32)


# ============================================================
# Chargement des données réelles depuis l'étape 1
# ============================================================

def load_real_data(
    db_url: str | None = None,
    num_users: int = 50,
    avg_interactions_per_user: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Charge les données réelles de l'étape 1 pour l'entraînement.

    Le catalogue de K-Dramas est lu depuis la base PostgreSQL de l'étape 1
    (vraies données collectées, 915 K-Dramas). Les notes individuelles par
    utilisateur sont simulées à partir des notes moyennes réelles.

    Args:
        db_url: URL de connexion PostgreSQL. Si None, lit depuis les
                variables d'environnement (SUPABASE_DB_URL ou DATABASE_URL).
        num_users: Nombre d'utilisateurs simulés pour le filtrage
                   collaboratif.
        avg_interactions_per_user: Nombre moyen de notes par utilisateur.

    Returns:
        Tuple (dramas_df, interactions_df) au format attendu par train().
    """
    from data_loader import load_real_data as _load

    return _load(
        db_url=db_url,
        num_users=num_users,
        avg_interactions_per_user=avg_interactions_per_user,
    )


# ============================================================
# Point d'entrée pour l'entraînement en CLI
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info("=== Entraînement du modèle de recommandation K-Drama ===")

    # Chargement des données réelles depuis l'étape 1
    dramas, interactions = load_real_data(num_users=50)

    # Entraînement
    model = HybridRecommender(alpha=0.6)
    metrics = model.train(dramas, interactions)

    # Sauvegarde
    model.save()

    # Test de recommandation
    results = model.recommend(user_id=1, top_k=5)
    print("\n=== Recommandations pour l'utilisateur 1 ===")
    for r in results:
        print(f"  - {r.title} (score: {r.score:.2f}) — {r.reason}")

    # Test de prédiction
    first_drama_id = int(dramas["drama_id"].iloc[0])
    pred = model.predict(user_id=1, drama_id=first_drama_id)
    print(f"\n=== Prédiction pour user 1, drama {first_drama_id} : {pred:.2f} ===")

    print("\n=== Entraînement terminé avec succès ===")
