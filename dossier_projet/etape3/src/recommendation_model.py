# ============================================================
# Modèle de recommandation hybride pour K-Dramas
# ============================================================

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = Path(__file__).parent / "model_artifacts"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_DEFAULT = 10
RANDOM_STATE = 42

_CLUSTER_STOPWORDS = {
    "actors",
    "ending",
    "genres",
    "genre",
    "drama",
    "dramas",
    "story",
    "stories",
    "kdrama",
    "kdramas",
    "positive",
    "negative",
    "mixed",
    "strongly",
    "overwhelmingly",
    "reception",
    "consensus",
    "viewers",
    "audience",
    "tone",
    # Common Korean actor surnames (avoid "lee vibe" type noise in cluster labels)
    "lee",
    "kim",
    "park",
    "shin",
    "jo",
    "han",
    "gang",
    "choi",
    "bae",
}


@dataclass
class RecommendationResult:
    drama_id: int
    title: str
    score: float
    genres: list[str] = field(default_factory=list)
    reason: str = ""
    explanation: str = ""
    synopsis: str = ""
    rating: float = 0.0
    year: int = 0
    episodes: int = 0
    poster: str = ""

    def to_dict(self) -> dict[str, Any]:
        explanation = self.explanation or self.reason
        return {
            "id": self.drama_id,
            "kdrama_id": self.drama_id,
            "drama_id": self.drama_id,
            "title": self.title,
            "titre": self.title,
            "score": round(float(self.score), 4),
            "genres": self.genres,
            "reason": explanation,
            "explanation": explanation,
            "synopsis": self.synopsis,
            "rating": round(float(self.rating), 1),
            "note_moyenne": round(float(self.rating), 1),
            "year": self.year,
            "date_diffusion": f"{self.year}-01-01" if self.year > 0 else None,
            "episodes": self.episodes,
            "nb_episodes": self.episodes,
            "poster": self.poster,
            "poster_url": self.poster,
            "predicted_rating": round(float(self.score), 1),
        }


@dataclass
class ModelMetrics:
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


class HybridRecommender:
    def __init__(
        self,
        alpha: float = 0.6,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha doit être entre 0 et 1, reçu : {alpha}")

        self.alpha = alpha
        self.embedding_model_name = embedding_model_name
        self.content_embeddings: np.ndarray | None = None
        self.collaborative_model: NearestNeighbors | None = None
        self.dramas_df: pd.DataFrame | None = None
        self.interactions_df: pd.DataFrame | None = None
        self.user_item_matrix: pd.DataFrame | None = None
        self.metrics = ModelMetrics()
        self._embedding_model = None
        self._is_trained = False
        self._drama_id_to_index: dict[int, int] = {}
        self.drama_clusters: dict[int, int] = {}
        self.cluster_labels: dict[int, str] = {}

    def train(
        self,
        dramas_df: pd.DataFrame,
        interactions_df: pd.DataFrame,
    ) -> ModelMetrics:
        start_time = time.time()
        self._validate_training_data(dramas_df, interactions_df)

        self.dramas_df = self._prepare_dramas_dataframe(dramas_df.copy())
        self.interactions_df = interactions_df.copy()

        self._load_embedding_model()
        self._generate_content_embeddings()
        self._build_content_clusters()
        self._build_user_item_matrix()
        self._train_collaborative_model()

        self.metrics.training_time_seconds = time.time() - start_time
        self.metrics.num_dramas = len(self.dramas_df)
        self.metrics.num_users = self.interactions_df["user_id"].nunique()
        self.metrics.num_interactions = len(self.interactions_df)
        self.metrics.embedding_dim = (
            int(self.content_embeddings.shape[1]) if self.content_embeddings is not None else 0
        )
        self.metrics.last_trained_at = pd.Timestamp.now().isoformat()
        self._is_trained = True
        logger.info(
            "Entraînement terminé en %.2fs (%d dramas, %d utilisateurs, %d interactions).",
            self.metrics.training_time_seconds,
            self.metrics.num_dramas,
            self.metrics.num_users,
            self.metrics.num_interactions,
        )
        return self.metrics

    def recommend(
        self,
        user_id: int | None = None,
        drama_id: int | None = None,
        top_k: int = TOP_K_DEFAULT,
        mood: str | None = None,
        text: str | None = None,
        genres: list[str] | None = None,
        actor_names: list[str] | None = None,
        happy_ending_only: bool | None = None,
        user_preferences: dict[str, Any] | None = None,
    ) -> list[RecommendationResult]:
        self._check_trained()
        if top_k <= 0:
            raise ValueError(f"top_k doit être > 0, reçu : {top_k}")

        user_preferences = user_preferences or {}
        resolved_genres = genres if genres is not None else user_preferences.get("favorite_genres")
        resolved_actors = (
            actor_names if actor_names is not None else user_preferences.get("favorite_actors")
        )
        resolved_happy = (
            happy_ending_only
            if happy_ending_only is not None
            else user_preferences.get("happy_ending_only", False)
        )
        query_text = self._build_query_text(mood, text, resolved_genres, resolved_actors, resolved_happy)

        positive_seed_ids = self._unique_ints(
            user_preferences.get("favorite_drama_ids", [])
            + user_preferences.get("interested_drama_ids", [])
        )
        negative_seed_ids = self._unique_ints(user_preferences.get("disliked_drama_ids", []))

        if user_id is not None and negative_seed_ids:
            logger.info(
                "User %d has %d disliked dramas: %s",
                user_id,
                len(negative_seed_ids),
                negative_seed_ids[:5],
            )

        has_request_context = any(
            [
                user_id is not None,
                drama_id is not None,
                bool(query_text),
                bool(resolved_genres),
                bool(resolved_actors),
                bool(positive_seed_ids),
                bool(resolved_happy),
            ]
        )
        if not has_request_context:
            raise ValueError(
                "Au moins un de user_id, drama_id, mood/text, genres, actor_names "
                "ou préférences utilisateur doit être fourni."
            )

        if user_id is not None:
            base_scores, exclude_ids, liked_ids = self._score_for_user(
                user_id=user_id,
                extra_positive_ids=positive_seed_ids,
                extra_negative_ids=negative_seed_ids,
            )
            mode = "user"
        elif drama_id is not None:
            base_scores, exclude_ids, liked_ids = self._score_for_drama(
                drama_id=drama_id,
                extra_positive_ids=positive_seed_ids,
                extra_negative_ids=negative_seed_ids,
            )
            mode = "item"
        else:
            base_scores = self._popular_scores()
            exclude_ids = set(negative_seed_ids)
            liked_ids = positive_seed_ids
            if positive_seed_ids:
                seeded_scores = self._seed_similarity_scores(positive_seed_ids)
                base_scores = 0.65 * seeded_scores + 0.35 * base_scores
            mode = "discovery"

        scores = base_scores.copy()
        before_count = len(scores)
        scores = scores.drop(labels=list(exclude_ids), errors="ignore")
        after_count = len(scores)
        if exclude_ids and before_count != after_count:
            logger.debug(
                "Excluded %d dramas (exclude_ids had %d items)",
                before_count - after_count,
                len(exclude_ids),
            )
        scores = scores[scores.index.isin(self.dramas_df["drama_id"].tolist())]

        if negative_seed_ids:
            penalty = self._seed_similarity_scores(negative_seed_ids).reindex(scores.index).fillna(0.0)
            scores = scores - penalty * 0.35

        genre_mask = self._match_mask(scores.index.tolist(), resolved_genres, "genre")
        actor_mask = self._match_mask(scores.index.tolist(), resolved_actors, "actor")
        query_scores = self._query_similarity_scores(query_text).reindex(scores.index).fillna(0.0)

        if not query_scores.empty and query_scores.max() > 0:
            # A free-text/mood request is an explicit, information-rich
            # signal from the user — it should strongly drive the ranking
            # rather than just nudge history-based scores, otherwise a
            # request like "a quiet drama set on an island" gets drowned out
            # by collaborative/history noise (especially for users with
            # little or synthetic interaction history). A specific written
            # request (`text`) gets the strongest weight; a short mood label
            # alone gets a slightly lighter one.
            query_weight = 0.8 if text else 0.6
            scores = (1 - query_weight) * scores + query_weight * query_scores

        scores = self._apply_preference_adjustments(
            scores=scores,
            genre_mask=genre_mask,
            actor_mask=actor_mask,
            top_k=top_k,
        )

        if resolved_happy:
            happy_mask = self._happy_ending_mask(scores.index.tolist())
            scores = scores[happy_mask]

        scores = scores[scores > 0].sort_values(ascending=False).head(top_k)

        results: list[RecommendationResult] = []
        for candidate_id, score in scores.items():
            info = self._get_drama_info(int(candidate_id))
            if not info:
                continue
            explanation = self._build_explanation(
                drama_id=int(candidate_id),
                mode=mode,
                liked_ids=liked_ids,
                requested_genres=resolved_genres or [],
                requested_actors=resolved_actors or [],
                happy_ending_only=bool(resolved_happy),
                query_text=query_text,
                genre_match=bool(genre_mask.get(candidate_id, False)),
                actor_match=bool(actor_mask.get(candidate_id, False)),
                query_score=float(query_scores.get(candidate_id, 0.0)),
            )
            results.append(
                RecommendationResult(
                    drama_id=int(candidate_id),
                    title=info["title"],
                    score=float(score),
                    genres=info.get("genres", []),
                    reason=explanation,
                    explanation=explanation,
                    synopsis=info.get("synopsis", ""),
                    rating=info.get("rating", 0.0),
                    year=info.get("year", 0),
                    episodes=info.get("episodes", 0),
                    poster=info.get("poster", ""),
                )
            )
        return results

    def predict(self, user_id: int, drama_id: int) -> float:
        self._check_trained()
        if self.dramas_df is None or self.content_embeddings is None:
            raise RuntimeError("Modèle incomplet.")
        if drama_id not in self._drama_id_to_index:
            raise ValueError(f"Drama {drama_id} introuvable dans le catalogue.")

        content_score = self._content_prediction(user_id, drama_id)
        collaborative_score = self._collaborative_prediction(user_id, drama_id)
        popularity_score = float(self._popular_scores().get(drama_id, 5.0))

        components = [content_score, popularity_score]
        if collaborative_score > 0:
            components.append(collaborative_score)

        predicted = self.alpha * content_score + (1 - self.alpha) * np.mean(components[1:])
        return float(np.clip(predicted, 0.0, 10.0))

    def save(self, model_dir: Path | str = DEFAULT_MODEL_DIR) -> None:
        model_dir = Path(model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        embedding_model_cache = self._embedding_model
        self._embedding_model = None
        joblib.dump(self, model_dir / "model.joblib", compress=3)
        self._embedding_model = embedding_model_cache

        if self.content_embeddings is not None:
            np.save(model_dir / "content_embeddings.npy", self.content_embeddings)

        with open(model_dir / "metrics.json", "w", encoding="utf-8") as file:
            json.dump(self.metrics.to_dict(), file, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, model_dir: Path | str = DEFAULT_MODEL_DIR) -> "HybridRecommender":
        model_dir = Path(model_dir)
        model_path = model_dir / "model.joblib"
        if not model_path.exists():
            raise FileNotFoundError(f"Fichier modèle introuvable : {model_path}")

        model = joblib.load(model_path)
        emb_path = model_dir / "content_embeddings.npy"
        if emb_path.exists():
            model.content_embeddings = np.load(emb_path)
        model._embedding_model = None
        return model

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_type": "HybridRecommender",
            "alpha": self.alpha,
            "embedding_model": self.embedding_model_name,
            "is_trained": self._is_trained,
            "metrics": self.metrics.to_dict() if self._is_trained else None,
        }

    def _validate_training_data(
        self,
        dramas_df: pd.DataFrame,
        interactions_df: pd.DataFrame,
    ) -> None:
        required_drama_cols = {"drama_id", "title", "synopsis", "genres"}
        required_interaction_cols = {"user_id", "drama_id", "rating"}
        if dramas_df.empty:
            raise ValueError("Le DataFrame des dramas est vide.")
        if interactions_df.empty:
            raise ValueError("Le DataFrame des interactions est vide.")

        missing_drama = required_drama_cols - set(dramas_df.columns)
        missing_interaction = required_interaction_cols - set(interactions_df.columns)
        if missing_drama:
            raise ValueError(f"Colonnes manquantes dans dramas_df : {missing_drama}")
        if missing_interaction:
            raise ValueError(f"Colonnes manquantes dans interactions_df : {missing_interaction}")
        if not pd.api.types.is_numeric_dtype(interactions_df["rating"]):
            raise ValueError("La colonne 'rating' doit être numérique.")

    def _prepare_dramas_dataframe(self, dramas_df: pd.DataFrame) -> pd.DataFrame:
        for column, default_value in {
            "synopsis": "",
            "genres": "",
            "principal_actors": "",
            "viewer_consensus": "",
            "sentiment_summary": "",
            "ending_type": "unknown",
            "poster": "",
        }.items():
            if column not in dramas_df.columns:
                dramas_df[column] = default_value
            dramas_df[column] = dramas_df[column].fillna(default_value)

        if "sentiment_score" not in dramas_df.columns:
            dramas_df["sentiment_score"] = 0.0
        dramas_df["sentiment_score"] = pd.to_numeric(
            dramas_df["sentiment_score"], errors="coerce"
        ).fillna(0.0)

        if "note_moyenne" not in dramas_df.columns:
            dramas_df["note_moyenne"] = 0.0
        dramas_df["note_moyenne"] = pd.to_numeric(
            dramas_df["note_moyenne"], errors="coerce"
        ).fillna(0.0)

        if "nb_episodes" not in dramas_df.columns:
            dramas_df["nb_episodes"] = 0
        dramas_df["nb_episodes"] = pd.to_numeric(
            dramas_df["nb_episodes"], errors="coerce"
        ).fillna(0).astype(int)

        dramas_df["drama_id"] = pd.to_numeric(dramas_df["drama_id"], errors="coerce").astype(int)
        dramas_df["title"] = dramas_df["title"].fillna("").astype(str)
        dramas_df["genre_list"] = dramas_df["genres"].apply(self._parse_list)
        dramas_df["actor_list"] = dramas_df["principal_actors"].apply(self._parse_list)
        dramas_df["genre_norm_set"] = dramas_df["genre_list"].apply(
            lambda items: {self._normalize_token(item) for item in items if item}
        )
        dramas_df["actor_norm_set"] = dramas_df["actor_list"].apply(
            lambda items: {self._normalize_token(item) for item in items if item}
        )
        dramas_df["ending_phrase"] = dramas_df.apply(self._build_ending_phrase, axis=1)
        dramas_df["content_text"] = dramas_df.apply(self._build_content_text, axis=1)
        self._drama_id_to_index = {
            int(drama_id): index
            for index, drama_id in enumerate(dramas_df["drama_id"].tolist())
        }
        return dramas_df

    def _load_embedding_model(self) -> None:
        if self._embedding_model is not None:
            return
        if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST") or os.getenv("DISABLE_SENTENCE_TRANSFORMERS") == "1":
            self._embedding_model = _TFIDFFallback()
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.embedding_model_name)
        except Exception:
            logger.warning("sentence-transformers indisponible, fallback TF-IDF activé.")
            self._embedding_model = _TFIDFFallback()

    def _generate_content_embeddings(self) -> None:
        if self.dramas_df is None:
            raise RuntimeError("dramas_df n'est pas initialisé.")
        texts = self.dramas_df["content_text"].astype(str).tolist()
        embeddings = self._embedding_model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        self.content_embeddings = normalize(embeddings, norm="l2")

    def _build_content_clusters(self) -> None:
        if self.dramas_df is None or self.content_embeddings is None:
            return

        num_dramas = len(self.dramas_df)
        if num_dramas < 2:
            only_id = int(self.dramas_df.iloc[0]["drama_id"])
            self.drama_clusters = {only_id: 0}
            self.cluster_labels = {0: "drama pick"}
            return

        num_clusters = max(2, min(8, int(np.sqrt(num_dramas))))
        num_clusters = min(num_clusters, num_dramas)
        features = np.hstack(
            [
                self.content_embeddings,
                self.dramas_df["sentiment_score"].to_numpy(dtype=float).reshape(-1, 1),
            ]
        )
        clusterer = KMeans(
            n_clusters=num_clusters,
            n_init=10,
            random_state=RANDOM_STATE,
        )
        labels = clusterer.fit_predict(features)
        self.drama_clusters = {
            int(drama_id): int(label)
            for drama_id, label in zip(self.dramas_df["drama_id"].tolist(), labels)
        }

        vectorizer = TfidfVectorizer(
            max_features=400,
            stop_words="english",
            ngram_range=(1, 2),
        )
        # Cluster labels should describe THEMES (plot, setting, dynamics),
        # not repeat the sentiment/ending/audience-reception signal that's
        # already surfaced separately in the explanation. Using content_text
        # here (which also embeds ending/tone phrases and viewer_consensus
        # boilerplate like "Strongly positive") caused labels such as
        # "positive, strongly positive, strongly" instead of real themes —
        # so cluster labeling uses a narrower, theme-only text source.
        label_source_texts = (
            self.dramas_df["synopsis"].astype(str)
            + " "
            + self.dramas_df["genres"].apply(
                lambda value: " ".join(self._parse_list(value))
            )
        )
        tfidf_matrix = vectorizer.fit_transform(label_source_texts)
        feature_names = np.array(vectorizer.get_feature_names_out())

        self.cluster_labels = {}
        for cluster_id in sorted(set(labels)):
            cluster_rows = np.where(labels == cluster_id)[0]
            cluster_slice = tfidf_matrix[cluster_rows]
            mean_scores = np.asarray(cluster_slice.mean(axis=0)).ravel()
            ranked_terms = feature_names[np.argsort(mean_scores)[::-1]]
            clean_terms = [
                term.replace("_", " ")
                for term in ranked_terms
                if term not in _CLUSTER_STOPWORDS
                and not any(stop in term.split() for stop in _CLUSTER_STOPWORDS)
            ]
            label = ", ".join(clean_terms[:3]).strip(", ")
            # Empty string (not "similar vibe") when no good theme keyword is
            # found: the consumer (_build_explanation) appends "... vibe"
            # itself, so a non-empty placeholder here would read as
            # "shares a similar vibe vibe".
            self.cluster_labels[int(cluster_id)] = label

    def _build_user_item_matrix(self) -> None:
        if self.interactions_df is None:
            raise RuntimeError("interactions_df n'est pas initialisé.")
        aggregated = (
            self.interactions_df.groupby(["user_id", "drama_id"], as_index=False)["rating"].mean()
        )
        self.user_item_matrix = aggregated.pivot_table(
            index="user_id",
            columns="drama_id",
            values="rating",
            fill_value=0.0,
        )

    def _train_collaborative_model(self) -> None:
        if self.user_item_matrix is None:
            raise RuntimeError("user_item_matrix n'est pas construit.")
        self.collaborative_model = NearestNeighbors(
            n_neighbors=min(20, self.user_item_matrix.shape[0]),
            metric="cosine",
            algorithm="brute",
        )
        self.collaborative_model.fit(self.user_item_matrix.values)

    def _score_for_user(
        self,
        user_id: int,
        extra_positive_ids: list[int],
        extra_negative_ids: list[int],
    ) -> tuple[pd.Series, set[int], list[int]]:
        if self.dramas_df is None:
            raise RuntimeError("Catalogue indisponible.")

        base_scores = self._popular_scores()
        liked_ids: list[int] = []
        exclude_ids: set[int] = set(extra_negative_ids)

        if self.user_item_matrix is not None and user_id in self.user_item_matrix.index:
            user_vector = self.user_item_matrix.loc[user_id].values.reshape(1, -1)
            seen_dramas = self.user_item_matrix.loc[user_id]
            seen_ids = [int(drama_id) for drama_id, rating in seen_dramas.items() if rating > 0]
            exclude_ids.update(seen_ids)

            rated = seen_dramas[seen_dramas > 0].sort_values(ascending=False)
            liked_ids.extend([int(drama_id) for drama_id in rated.head(5).index.tolist()])

            collaborative_scores = self._collaborative_scores_for_user_vector(
                user_vector=user_vector,
                exclude_ids=exclude_ids,
            )
            content_scores = self._seed_similarity_scores(
                seed_ids=seen_ids + extra_positive_ids,
                seed_weights=[
                    float(seen_dramas.get(drama_id, 8.0)) for drama_id in seen_ids
                ]
                + [9.5 for _ in extra_positive_ids],
            )
            base_scores = (
                self.alpha * content_scores
                + (1 - self.alpha) * collaborative_scores
                + 0.15 * self._popular_scores()
            )
        else:
            liked_ids.extend(extra_positive_ids)
            if extra_positive_ids:
                base_scores = 0.7 * self._seed_similarity_scores(extra_positive_ids) + 0.3 * base_scores

        if extra_positive_ids:
            exclude_ids.update(extra_positive_ids)
            liked_ids = self._unique_ints(liked_ids + extra_positive_ids)
        return base_scores, exclude_ids, liked_ids

    def _score_for_drama(
        self,
        drama_id: int,
        extra_positive_ids: list[int],
        extra_negative_ids: list[int],
    ) -> tuple[pd.Series, set[int], list[int]]:
        if drama_id not in self._drama_id_to_index:
            raise ValueError(f"Drama {drama_id} introuvable dans le catalogue.")

        seed_scores = self._seed_similarity_scores([drama_id] + extra_positive_ids)
        co_occurrence = self._co_occurrence_scores(drama_id)
        base_scores = self.alpha * seed_scores + (1 - self.alpha) * co_occurrence + 0.15 * self._popular_scores()
        exclude_ids = {drama_id, *extra_positive_ids, *extra_negative_ids}
        liked_ids = self._unique_ints([drama_id] + extra_positive_ids)
        return base_scores, exclude_ids, liked_ids

    def _collaborative_scores_for_user_vector(
        self,
        user_vector: np.ndarray,
        exclude_ids: set[int],
    ) -> pd.Series:
        if self.user_item_matrix is None or self.collaborative_model is None:
            return self._popular_scores()

        distances, indices = self.collaborative_model.kneighbors(user_vector)
        similar_users = self.user_item_matrix.iloc[indices[0]]
        weights = 1.0 - distances[0]
        weights = np.where(weights <= 0, 0.05, weights)
        weighted_scores = np.average(similar_users.values, axis=0, weights=weights)
        series = pd.Series(weighted_scores, index=self.user_item_matrix.columns, dtype=float)
        series = series.drop(labels=list(exclude_ids), errors="ignore")
        return self._scale_series(series)

    def _co_occurrence_scores(self, drama_id: int) -> pd.Series:
        if self.interactions_df is None:
            return self._popular_scores()
        users = self.interactions_df[self.interactions_df["drama_id"] == drama_id]["user_id"].unique()
        if len(users) == 0:
            return self._popular_scores()
        related = self.interactions_df[
            (self.interactions_df["user_id"].isin(users))
            & (self.interactions_df["drama_id"] != drama_id)
        ]
        if related.empty:
            return self._popular_scores()
        scores = related.groupby("drama_id")["rating"].mean()
        return self._scale_series(scores).reindex(self.dramas_df["drama_id"]).fillna(0.0)

    def _seed_similarity_scores(
        self,
        seed_ids: list[int],
        seed_weights: list[float] | None = None,
    ) -> pd.Series:
        if self.content_embeddings is None or self.dramas_df is None:
            return self._popular_scores()

        valid_seed_ids = [seed_id for seed_id in seed_ids if seed_id in self._drama_id_to_index]
        if not valid_seed_ids:
            return self._popular_scores()

        seed_indices = [self._drama_id_to_index[seed_id] for seed_id in valid_seed_ids]
        candidate_sims = self.content_embeddings @ self.content_embeddings[seed_indices].T
        weights = np.array(
            seed_weights[: len(valid_seed_ids)] if seed_weights else [1.0] * len(valid_seed_ids),
            dtype=float,
        )
        weighted_scores = candidate_sims @ weights / np.sum(np.abs(weights))
        series = pd.Series(weighted_scores, index=self.dramas_df["drama_id"], dtype=float)
        return self._scale_series(series)

    def _popular_scores(self) -> pd.Series:
        if self.dramas_df is None:
            return pd.Series(dtype=float)
        if self.interactions_df is not None and not self.interactions_df.empty:
            series = self.interactions_df.groupby("drama_id")["rating"].mean()
        else:
            series = self.dramas_df.set_index("drama_id")["note_moyenne"]
        return self._scale_series(series).reindex(self.dramas_df["drama_id"]).fillna(0.0)

    def _query_similarity_scores(self, query_text: str) -> pd.Series:
        if not query_text or self.content_embeddings is None or self.dramas_df is None:
            return pd.Series(0.0, index=self.dramas_df["drama_id"] if self.dramas_df is not None else [])
        query_embedding = self._embedding_model.encode(
            [query_text],
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        query_embedding = normalize(query_embedding, norm="l2")[0]
        cosine_scores = self.content_embeddings @ query_embedding

        # Sentence embeddings average an entire concatenated document
        # (synopsis + genres + actors + ending/sentiment + review snippet),
        # which dilutes short/literal keywords the user actually typed (e.g.
        # "island") when the rest of that long text is about something else.
        # Whenever the query has a literal keyword match somewhere in the
        # catalog, that match should DOMINATE the ranking — cosine
        # similarity is kept only as a tie-breaker among equally-matching
        # candidates, and as the sole signal when there is no literal match
        # at all (e.g. abstract mood words like "heartwarming").
        keyword_hits = self._keyword_overlap_scores(query_text)
        combined = cosine_scores + keyword_hits * 10.0
        return self._scale_series(pd.Series(combined, index=self.dramas_df["drama_id"], dtype=float))

    _QUERY_STOPWORDS = {
        "about", "after", "before", "drama", "dramas", "episode", "episodes",
        "series", "show", "shows", "story", "stories", "kdrama", "kdramas",
        "with", "that", "this", "have", "from", "want", "like", "some",
        "into", "onto", "your", "their", "there", "where", "which", "while",
    }

    def _keyword_overlap_scores(self, query_text: str) -> np.ndarray:
        """Counts literal (case-insensitive) keyword hits between the query
        and each drama's title/synopsis/review snippet, ignoring short/common
        words. Returns an array aligned with dramas_df row order.
        """
        if self.dramas_df is None:
            return np.zeros(0)
        keywords = [
            word
            for word in re.findall(r"[a-zA-Z]{4,}", query_text.lower())
            if word not in self._QUERY_STOPWORDS
        ]
        if not keywords:
            return np.zeros(len(self.dramas_df))

        review_snippets = self.dramas_df.get(
            "review_snippet", pd.Series("", index=self.dramas_df.index)
        ).astype(str)
        haystacks = (
            self.dramas_df["title"].astype(str)
            + " "
            + self.dramas_df["synopsis"].astype(str)
            + " "
            + review_snippets
        ).str.lower()

        return haystacks.apply(
            lambda text: sum(1 for kw in keywords if kw in text)
        ).to_numpy(dtype=float)

    def _apply_preference_adjustments(
        self,
        scores: pd.Series,
        genre_mask: pd.Series,
        actor_mask: pd.Series,
        top_k: int,
    ) -> pd.Series:
        adjusted = scores.copy()
        if not genre_mask.empty and genre_mask.any():
            aligned_genre_mask = genre_mask.reindex(adjusted.index).fillna(False)
            adjusted.loc[aligned_genre_mask] += 1.1
            if int(genre_mask.sum()) >= min(top_k, 3):
                adjusted = adjusted[aligned_genre_mask]
        if not actor_mask.empty and actor_mask.any():
            aligned_actor_mask = actor_mask.reindex(adjusted.index).fillna(False)
            adjusted.loc[aligned_actor_mask] += 1.2
            if int(actor_mask.sum()) >= min(top_k, 2) and len(adjusted[aligned_actor_mask]) > 0:
                adjusted = adjusted[aligned_actor_mask]
        return adjusted

    def _happy_ending_mask(self, drama_ids: list[int]) -> pd.Series:
        rows = self.dramas_df.set_index("drama_id").reindex(drama_ids)
        mask = rows["ending_type"].astype(str).str.lower().eq("happy")
        mask.index = drama_ids
        return mask.fillna(False)

    def _match_mask(
        self,
        drama_ids: list[int],
        requested_values: list[str] | None,
        field_type: str,
    ) -> pd.Series:
        if self.dramas_df is None or not requested_values:
            return pd.Series(False, index=drama_ids, dtype=bool)

        normalized_requested = {
            self._normalize_token(value)
            for value in requested_values
            if isinstance(value, str) and value.strip()
        }
        if not normalized_requested:
            return pd.Series(False, index=drama_ids, dtype=bool)

        field_name = "genre_norm_set" if field_type == "genre" else "actor_norm_set"
        rows = self.dramas_df.set_index("drama_id").reindex(drama_ids)
        mask = rows[field_name].apply(
            lambda available: bool(set(available or set()) & normalized_requested)
        )
        mask.index = drama_ids
        return mask.fillna(False)

    def _build_explanation(
        self,
        drama_id: int,
        mode: str,
        liked_ids: list[int],
        requested_genres: list[str],
        requested_actors: list[str],
        happy_ending_only: bool,
        query_text: str,
        genre_match: bool,
        actor_match: bool,
        query_score: float,
    ) -> str:
        info = self._get_drama_info(drama_id) or {}
        parts: list[str] = []

        similar_titles = self._top_similar_seed_titles(drama_id, liked_ids)
        if similar_titles:
            parts.append(f"Because you liked {', '.join(similar_titles)}")
        elif mode == "item" and liked_ids:
            seed_title = self._get_drama_title(liked_ids[0])
            if seed_title:
                parts.append(f"Close in style to {seed_title}")

        if genre_match and requested_genres:
            parts.append(f"matches your {requested_genres[0]} preference")
        if actor_match and requested_actors:
            parts.append(f"features {requested_actors[0]} or a similar cast vibe")
        if happy_ending_only and str(info.get("ending_type", "")).lower() == "happy":
            parts.append("keeps a happy ending")
        if query_text and query_score > 4.0:
            parts.append("fits the mood and tone you asked for")

        cluster_label = info.get("cluster_label", "")
        if cluster_label and cluster_label != "similar vibe":
            parts.append(f"shares a {cluster_label} vibe")

        if not parts:
            parts.append("Strong overall match based on content and audience preferences")
        return ". ".join(parts[:3]) + "."

    def _top_similar_seed_titles(self, drama_id: int, seed_ids: list[int]) -> list[str]:
        if self.content_embeddings is None or drama_id not in self._drama_id_to_index:
            return []
        target_idx = self._drama_id_to_index[drama_id]
        ranked: list[tuple[float, str]] = []
        for seed_id in self._unique_ints(seed_ids):
            if seed_id == drama_id or seed_id not in self._drama_id_to_index:
                continue
            seed_idx = self._drama_id_to_index[seed_id]
            similarity = float(np.dot(self.content_embeddings[target_idx], self.content_embeddings[seed_idx]))
            title = self._get_drama_title(seed_id)
            if title:
                ranked.append((similarity, title))
        ranked.sort(reverse=True)
        return [title for _, title in ranked[:2]]

    def _content_prediction(self, user_id: int, drama_id: int) -> float:
        if self.user_item_matrix is None or self.content_embeddings is None:
            return float(self._popular_scores().get(drama_id, 5.0))
        if user_id not in self.user_item_matrix.index:
            return float(self._popular_scores().get(drama_id, 5.0))

        user_ratings = self.user_item_matrix.loc[user_id]
        rated = user_ratings[user_ratings > 0]
        if rated.empty:
            return float(self._popular_scores().get(drama_id, 5.0))

        target_idx = self._drama_id_to_index[drama_id]
        sims: list[float] = []
        weights: list[float] = []
        for seen_id, rating in rated.items():
            if int(seen_id) not in self._drama_id_to_index:
                continue
            seen_idx = self._drama_id_to_index[int(seen_id)]
            sims.append(float(np.dot(self.content_embeddings[target_idx], self.content_embeddings[seen_idx])))
            weights.append(float(rating))
        if not sims:
            return float(self._popular_scores().get(drama_id, 5.0))

        value = np.average(np.array(sims) * 10.0, weights=weights)
        return float(np.clip(value, 0.0, 10.0))

    def _collaborative_prediction(self, user_id: int, drama_id: int) -> float:
        if self.user_item_matrix is None or self.collaborative_model is None:
            return 0.0
        if user_id not in self.user_item_matrix.index or drama_id not in self.user_item_matrix.columns:
            return 0.0

        user_vector = self.user_item_matrix.loc[user_id].values.reshape(1, -1)
        distances, indices = self.collaborative_model.kneighbors(user_vector)
        similar_users = self.user_item_matrix.iloc[indices[0]]
        ratings = similar_users[drama_id]
        ratings = ratings[ratings > 0]
        if ratings.empty:
            return 0.0
        return float(np.clip(ratings.mean(), 0.0, 10.0))

    def _check_trained(self) -> None:
        if not self._is_trained:
            raise RuntimeError("Le modèle n'est pas entraîné. Appelez train() d'abord.")

    def _get_drama_title(self, drama_id: int) -> str:
        info = self._get_drama_info(drama_id)
        return info["title"] if info else ""

    def _get_drama_info(self, drama_id: int) -> dict[str, Any] | None:
        if self.dramas_df is None:
            return None
        row = self.dramas_df[self.dramas_df["drama_id"] == drama_id]
        if row.empty:
            return None
        item = row.iloc[0]

        year = 0
        date_value = item.get("date_diffusion")
        if isinstance(date_value, str) and date_value:
            try:
                year = int(date_value.split("-")[0])
            except (ValueError, IndexError):
                year = 0
        elif hasattr(date_value, "year"):
            try:
                year = int(date_value.year)
            except Exception:
                year = 0

        poster = str(item.get("poster", "") or item.get("poster_url", "") or "").strip()
        if not poster or poster.lower() in {"none", "nan"}:
            poster = "https://via.placeholder.com/400x600?text=No+Poster"

        cluster_id = self.drama_clusters.get(drama_id)
        cluster_label = self.cluster_labels.get(cluster_id, "") if cluster_id is not None else ""

        return {
            "drama_id": drama_id,
            "title": str(item.get("title", "Unknown")),
            "genres": list(item.get("genre_list", self._parse_list(item.get("genres", "")))),
            "synopsis": str(item.get("synopsis", "")),
            "rating": float(item.get("note_moyenne", 0.0) or 0.0),
            "year": year,
            "episodes": int(item.get("nb_episodes", 0) or 0),
            "poster": poster,
            "ending_type": str(item.get("ending_type", "unknown")),
            "sentiment_score": float(item.get("sentiment_score", 0.0) or 0.0),
            "viewer_consensus": str(item.get("viewer_consensus", "")),
            "principal_actors": list(
                item.get("actor_list", self._parse_list(item.get("principal_actors", "")))
            ),
            "cluster_label": cluster_label,
        }

    def _build_content_text(self, row: pd.Series) -> str:
        title = str(row.get("title", "")).strip()
        synopsis = str(row.get("synopsis", "")).strip()
        genres = ", ".join(self._parse_list(row.get("genres", "")))
        actors = ", ".join(self._parse_list(row.get("principal_actors", "")))
        ending_phrase = self._build_ending_phrase(row)
        consensus = str(row.get("viewer_consensus", "")).strip()
        summary = str(row.get("sentiment_summary", "")).strip()
        # Real viewer review text (kdrama.drama_reviews) often describes plot
        # details, settings and themes (e.g. "on a remote island") that the
        # short synopsis omits, improving free-text/mood semantic matching.
        review_snippet = str(row.get("review_snippet", "")).strip()
        parts = [
            title,
            synopsis,
            f"Genres: {genres}" if genres else "",
            f"Actors: {actors}" if actors else "",
            ending_phrase,
            summary,
            consensus,
            review_snippet,
        ]
        return " ".join(part for part in parts if part)

    def _build_ending_phrase(self, row: pd.Series) -> str:
        ending_type = str(row.get("ending_type", "unknown") or "unknown").strip().lower()
        sentiment_score = float(row.get("sentiment_score", 0.0) or 0.0)
        if ending_type == "happy":
            tone = "uplifting" if sentiment_score >= 0.35 else "gentle"
            return f"Ending: happy and {tone}."
        if ending_type == "sad":
            return "Ending: sad and emotional."
        if ending_type == "bittersweet":
            return "Ending: bittersweet and reflective."
        if sentiment_score >= 0.45:
            return "Tone: optimistic and emotionally rewarding."
        if sentiment_score <= -0.2:
            return "Tone: darker and emotionally intense."
        return "Tone: balanced and character-driven."

    @staticmethod
    def _parse_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    decoded = json.loads(stripped)
                    raw_items = decoded if isinstance(decoded, list) else [decoded]
                except json.JSONDecodeError:
                    raw_items = stripped.split(",")
            else:
                raw_items = stripped.split(",")
        else:
            raw_items = [value]

        items: list[str] = []
        for item in raw_items:
            clean = str(item).strip().strip("[]\"'")
            if clean and clean.lower() != "nan" and clean not in items:
                items.append(clean)
        return items

    @staticmethod
    def _normalize_token(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        return re.sub(r"\s+", " ", normalized)

    @staticmethod
    def _scale_series(series: pd.Series) -> pd.Series:
        if series.empty:
            return series.astype(float)
        series = series.astype(float).fillna(0.0)
        minimum = float(series.min())
        maximum = float(series.max())
        if maximum - minimum < 1e-9:
            return pd.Series(
                np.where(series > 0, 10.0, 0.0),
                index=series.index,
                dtype=float,
            )
        return ((series - minimum) / (maximum - minimum) * 10.0).astype(float)

    @staticmethod
    def _unique_ints(values: list[Any]) -> list[int]:
        unique: list[int] = []
        for value in values:
            try:
                integer = int(value)
            except (TypeError, ValueError):
                continue
            if integer not in unique:
                unique.append(integer)
        return unique

    @staticmethod
    def _build_query_text(
        mood: str | None,
        text: str | None,
        genres: list[str] | None,
        actor_names: list[str] | None,
        happy_ending_only: bool | None,
    ) -> str:
        parts: list[str] = []
        if mood:
            parts.append(f"Mood: {mood}")
        if text:
            parts.append(text.strip())
        if genres:
            parts.append(f"Preferred genres: {', '.join(genres)}")
        if actor_names:
            parts.append(f"Preferred actors: {', '.join(actor_names)}")
        if happy_ending_only:
            parts.append("Needs a happy ending")
        return " ".join(part for part in parts if part)


class _TFIDFFallback:
    def __init__(self) -> None:
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
        del show_progress_bar, convert_to_numpy
        if not self._is_fitted:
            embeddings = self.vectorizer.fit_transform(texts).toarray()
            self._is_fitted = True
        else:
            embeddings = self.vectorizer.transform(texts).toarray()
        return embeddings.astype(np.float32)


def load_real_data(
    db_url: str | None = None,
    num_users: int = 50,
    avg_interactions_per_user: int = 8,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    from data_loader import load_real_data as _load

    return _load(
        db_url=db_url,
        num_users=num_users,
        avg_interactions_per_user=avg_interactions_per_user,
    )
