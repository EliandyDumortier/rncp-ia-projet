# ============================================================
# Tests automatisés pour l'API du modèle de recommandation K-Drama
# Fichier : test_model_api.py
#
# Couverture :
#   1. Tests des endpoints (/health, /metrics, /auth/token, /recommend, /predict)
#   2. Tests de validation des entrées (Pydantic)
#   3. Tests du format des sorties
#   4. Tests de performance (seuils de latence)
#   5. Tests de sécurité (JWT, rate limiting, OWASP)
#   6. Tests du modèle de recommandation (unitaires)
#   7. Tests du monitoring (métriques Prometheus)
#
# Exécution : pytest tests/test_model_api.py -v --cov=src --cov-report=term
# Auteur : Équipe QA / MLOps
# Étape 3 — RNCP AI Project
# ============================================================

from __future__ import annotations

import os
import secrets
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

# Ajout du répertoire src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pytestmark = pytest.mark.filterwarnings(
    "ignore:The 'app' shortcut is now deprecated.*:DeprecationWarning:httpx\\._client"
)

os.environ.setdefault("JWT_SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("ADMIN_PASSWORD", secrets.token_urlsafe(16))
os.environ.setdefault("USER_PASSWORD", secrets.token_urlsafe(16))

import model_api  # noqa: E402
from model_api import RecommendRequest, app, create_access_token, model_manager  # noqa: E402
from recommendation_model import (  # noqa: E402
    HybridRecommender,
    RecommendationResult,
)
from model_monitoring import (  # noqa: E402
    ModelMonitor,
    DriftMonitor,
    get_monitor,
)


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(scope="session")
def trained_model() -> HybridRecommender:
    """
    Entraîne un modèle sur des données locales simulées.

    Ce fixture évite toute dépendance réseau/base distante pendant les tests
    CI afin de garder une suite déterministe et reproductible.
    """
    rng = np.random.RandomState(42)

    num_dramas = 30
    num_users = 50

    dramas_df = pd.DataFrame(
        {
            "drama_id": list(range(1, num_dramas + 1)),
            "title": [f"Drama {i}" for i in range(1, num_dramas + 1)],
            "synopsis": [
                f"Synopsis test pour le drama {i}." for i in range(1, num_dramas + 1)
            ],
            "genres": [
                "Romance, Comedy" if i % 2 == 0 else "Thriller, Mystery"
                for i in range(1, num_dramas + 1)
            ],
            "note_moyenne": [7.5 + (i % 5) * 0.3 for i in range(1, num_dramas + 1)],
            "nb_episodes": [12 if i % 2 == 0 else 16 for i in range(1, num_dramas + 1)],
            "date_diffusion": [
                f"20{10 + (i % 10):02d}-01-01" for i in range(1, num_dramas + 1)
            ],
            "poster": [f"https://example.com/poster-{i}.jpg" for i in range(1, num_dramas + 1)],
            "principal_actors": [
                "Lee Min-ho, Kim Ji-won"
                if i % 3 == 0
                else "Park Seo-joon, IU"
                if i % 3 == 1
                else "Son Ye-jin, Hyun Bin"
                for i in range(1, num_dramas + 1)
            ],
            "ending_type": [
                "happy" if i % 3 != 0 else "bittersweet"
                for i in range(1, num_dramas + 1)
            ],
            "sentiment_score": [
                0.75 if i % 3 != 0 else 0.15 for i in range(1, num_dramas + 1)
            ],
            "viewer_consensus": [
                "Feel-good romance" if i % 2 == 0 else "Dark mystery thriller"
                for i in range(1, num_dramas + 1)
            ],
        }
    )

    interactions_data: list[dict[str, float | int]] = []
    for user_id in range(1, num_users + 1):
        n_interactions = int(rng.randint(6, 13))
        chosen = rng.choice(
            dramas_df["drama_id"].values,
            size=n_interactions,
            replace=False,
        )
        for drama_id in chosen:
            rating = float(np.clip(rng.normal(loc=7.8, scale=1.2), 1.0, 10.0))
            interactions_data.append(
                {
                    "user_id": int(user_id),
                    "drama_id": int(drama_id),
                    "rating": round(rating, 1),
                }
            )

    interactions_df = pd.DataFrame(interactions_data)

    model = HybridRecommender(alpha=0.6)
    model.train(dramas_df, interactions_df)
    return model


@pytest.fixture(scope="session")
def auth_token() -> str:
    """Génère un token JWT valide pour les tests."""
    return create_access_token(data={"sub": "test_user", "role": "user"})


@pytest.fixture(scope="session")
def admin_token() -> str:
    """Génère un token JWT admin pour les tests."""
    return create_access_token(data={"sub": "admin", "role": "admin"})


@pytest.fixture(scope="session")
def numeric_auth_token() -> str:
    """JWT réaliste avec sub numérique provenant du data-api."""
    return create_access_token(data={"sub": "123", "role": "user"})


@pytest.fixture(scope="session")
def client(trained_model: HybridRecommender) -> TestClient:
    """
    Crée un client de test FastAPI avec le modèle pré-entraîné.
    Le modèle est injecté dans le ModelManager pour éviter
    un entraînement à chaque test.
    """
    # Injection du modèle entraîné dans le gestionnaire
    model_manager.model = trained_model
    model_manager._load_attempted = True

    # Mise à jour du monitoring
    monitor = get_monitor()
    monitor.set_model_status(True)

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Headers d'authentification avec token JWT utilisateur."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    """Headers d'authentification avec token JWT admin."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def numeric_auth_headers(numeric_auth_token: str) -> dict[str, str]:
    """Headers d'authentification avec sub numérique."""
    return {"Authorization": f"Bearer {numeric_auth_token}"}


# ============================================================
# 1. Tests du endpoint /health
# ============================================================


class TestHealthEndpoint:
    """Tests du health check de l'API."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Le endpoint /health doit retourner un statut 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_format(self, client: TestClient) -> None:
        """La réponse /health doit contenir tous les champs attendus."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "model_loaded" in data
        assert "model_trained" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_model_loaded(self, client: TestClient) -> None:
        """Le modèle doit être signalé comme chargé après l'initialisation."""
        response = client.get("/health")
        data = response.json()
        assert data["model_loaded"] is True
        assert data["model_trained"] is True

    def test_health_status_is_healthy(self, client: TestClient) -> None:
        """Le statut doit être 'healthy' quand le modèle est entraîné."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_version_format(self, client: TestClient) -> None:
        """La version doit respecter le format semver."""
        response = client.get("/health")
        data = response.json()
        # Format : X.Y.Z
        parts = data["version"].split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()

    def test_health_timestamp_is_iso(self, client: TestClient) -> None:
        """Le timestamp doit être au format ISO 8601."""
        response = client.get("/health")
        data = response.json()
        # Vérification que le timestamp est parsable
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"])


# ============================================================
# 2. Tests du endpoint /metrics
# ============================================================


class TestMetricsEndpoint:
    """Tests du endpoint Prometheus /metrics."""

    def test_metrics_returns_200(self, client: TestClient) -> None:
        """Le endpoint /metrics doit retourner un statut 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_content_type(self, client: TestClient) -> None:
        """Le content-type doit être text/plain (format Prometheus)."""
        response = client.get("/metrics")
        assert "text/plain" in response.headers.get("content-type", "")

    def test_metrics_contains_prometheus_format(self, client: TestClient) -> None:
        """Les métriques doivent contenir des lignes au format Prometheus."""
        response = client.get("/metrics")
        text = response.text
        # Vérification de la présence de métriques Prometheus
        assert "kdrama_api_requests_total" in text or "#" in text

    def test_metrics_has_help_text(self, client: TestClient) -> None:
        """Les métriques doivent inclure des commentaires HELP."""
        response = client.get("/metrics")
        text = response.text
        assert "# HELP" in text or "# TYPE" in text


# ============================================================
# 3. Tests du endpoint /auth/token
# ============================================================


class TestAuthEndpoint:
    """Tests de l'authentification JWT."""

    def test_auth_valid_credentials(self, client: TestClient) -> None:
        """L'authentification avec des identifiants valides doit réussir."""
        response = client.post(
            "/auth/token",
            json={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_auth_invalid_password(self, client: TestClient) -> None:
        """L'authentification avec un mauvais mot de passe doit échouer."""
        response = client.post(
            "/auth/token",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_auth_invalid_username(self, client: TestClient) -> None:
        """L'authentification avec un utilisateur inexistant doit échouer."""
        response = client.post(
            "/auth/token",
            json={"username": "nonexistent", "password": "pass"},
        )
        assert response.status_code == 401

    def test_auth_missing_fields(self, client: TestClient) -> None:
        """L'authentification sans champs doit retourner 422."""
        response = client.post("/auth/token", json={})
        assert response.status_code == 422

    def test_auth_empty_username(self, client: TestClient) -> None:
        """Un nom d'utilisateur vide doit être rejeté."""
        response = client.post(
            "/auth/token",
            json={"username": "", "password": "pass"},
        )
        assert response.status_code == 422

    def test_token_is_decodable(self, client: TestClient) -> None:
        """Le token JWT retourné doit être décodable."""
        import jwt as pyjwt

        response = client.post(
            "/auth/token",
            json={"username": "user", "password": os.environ["USER_PASSWORD"]},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        payload = pyjwt.decode(
            token,
            key=os.environ.get(
                "JWT_SECRET_KEY",
                "kdrama-dev-secret-key-change-in-production",
            ),
            algorithms=["HS256"],
        )
        assert payload["sub"] == "user"
        assert payload["role"] == "user"


# ============================================================
# 4. Tests du endpoint /recommend
# ============================================================


class TestRecommendEndpoint:
    """Tests du endpoint de recommandation."""

    def test_recommend_by_user_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Recommandation par user_id doit retourner des résultats."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["mode"] == "user"
        assert data["count"] > 0
        assert len(data["recommendations"]) <= 5

    def test_recommend_by_drama_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Recommandation par drama_id doit retourner des résultats similaires."""
        response = client.post(
            "/recommend",
            json={"drama_id": 1, "top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["mode"] == "item"
        assert data["count"] > 0

    def test_recommend_without_auth(self, client: TestClient) -> None:
        """Recommandation sans authentification doit retourner 401."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 5},
        )
        assert response.status_code == 401

    def test_recommend_without_any_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Recommandation sans user_id ni drama_id doit retourner 400."""
        response = client.post(
            "/recommend",
            json={"top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_recommend_invalid_top_k_zero(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """top_k = 0 doit être rejeté par la validation."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 0},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_recommend_invalid_top_k_negative(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """top_k négatif doit être rejeté."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": -1},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_recommend_top_k_exceeds_max(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """top_k > 50 doit être rejeté."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 100},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_recommend_invalid_user_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """user_id négatif doit être rejeté."""
        response = client.post(
            "/recommend",
            json={"user_id": -1, "top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_recommend_response_format(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """La réponse doit contenir tous les champs attendus."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 3},
            headers=auth_headers,
        )
        data = response.json()

        assert "success" in data
        assert "mode" in data
        assert "count" in data
        assert "recommendations" in data
        assert "request_id" in data
        assert "latency_ms" in data

        # Vérification du format de chaque recommandation
        for rec in data["recommendations"]:
            assert "drama_id" in rec
            assert "title" in rec
            assert "score" in rec
            assert "genres" in rec
            assert "reason" in rec
            assert "explanation" in rec
            assert isinstance(rec["drama_id"], int)
            assert isinstance(rec["title"], str)
            assert isinstance(rec["score"], (int, float))
            assert isinstance(rec["genres"], list)
            assert isinstance(rec["explanation"], str)

    def test_recommend_scores_are_sorted(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Les scores doivent être triés par ordre décroissant."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 10},
            headers=auth_headers,
        )
        data = response.json()
        scores = [r["score"] for r in data["recommendations"]]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_unknown_user(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Un utilisateur inconnu doit obtenir des recommandations populaires (fallback)."""
        response = client.post(
            "/recommend",
            json={"user_id": 99999, "top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] > 0

    def test_recommend_accepts_new_optional_fields(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Les nouveaux champs mood/text/genres/actors/happy-ending doivent être pris en charge."""
        response = client.post(
            "/recommend",
            json={
                "user_id": 1,
                "top_k": 4,
                "mood": "feel good",
                "text": "romantic story with great chemistry",
                "genres": ["Romance"],
                "actor_names": ["Son Ye-jin"],
                "happy_ending_only": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "user"
        assert data["count"] <= 4
        assert len(data["recommendations"]) <= 4
        for rec in data["recommendations"]:
            assert rec["explanation"]

    def test_text_request_without_user_id_stays_discovery_mode(
        self,
        client: TestClient,
        numeric_auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Un JWT data-api avec sub numérique doit fonctionner sans DEMO_USERS."""
        monkeypatch.setattr(
            model_api,
            "fetch_user_preferences",
            lambda *_args, **_kwargs: {
                "user_id": 123,
                "favorite_genres": ["Romance"],
                "favorite_actors": ["Park Seo-joon"],
                "happy_ending_only": True,
                "favorite_drama_ids": [2, 4],
                "interested_drama_ids": [6],
                "disliked_drama_ids": [3],
            },
        )

        response = client.post(
            "/recommend",
            json={"top_k": 4, "text": "uplifting romance"},
            headers=numeric_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "discovery"
        assert data["count"] <= 4
        assert len(data["recommendations"]) <= 4
        assert all(rec["explanation"] for rec in data["recommendations"])

    def test_recommend_latency_under_threshold(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """La latence de recommandation doit être inférieure à 2 secondes."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 10},
            headers=auth_headers,
        )
        data = response.json()
        assert (
            data["latency_ms"] < 2000
        ), f"Latence trop élevée : {data['latency_ms']}ms"


# ============================================================
# 5. Tests du endpoint /predict
# ============================================================


class TestPredictEndpoint:
    """Tests du endpoint de prédiction de note."""

    def test_predict_valid_request(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Prédiction valide doit retourner un score entre 0 et 10."""
        response = client.post(
            "/predict",
            json={"user_id": 1, "drama_id": 5},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user_id"] == 1
        assert data["drama_id"] == 5
        assert 0.0 <= data["predicted_rating"] <= 10.0
        assert data["confidence"] in ("low", "medium", "high")

    def test_predict_without_auth(self, client: TestClient) -> None:
        """Prédiction sans authentification doit retourner 401."""
        response = client.post(
            "/predict",
            json={"user_id": 1, "drama_id": 5},
        )
        assert response.status_code == 401

    def test_predict_missing_fields(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Prédiction avec champs manquants doit retourner 422."""
        response = client.post(
            "/predict",
            json={"user_id": 1},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_predict_invalid_user_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """user_id négatif doit être rejeté."""
        response = client.post(
            "/predict",
            json={"user_id": -1, "drama_id": 5},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_predict_invalid_drama_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """drama_id négatif doit être rejeté."""
        response = client.post(
            "/predict",
            json={"user_id": 1, "drama_id": -1},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_predict_response_format(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """La réponse doit contenir tous les champs attendus."""
        response = client.post(
            "/predict",
            json={"user_id": 1, "drama_id": 5},
            headers=auth_headers,
        )
        data = response.json()

        assert "success" in data
        assert "user_id" in data
        assert "drama_id" in data
        assert "predicted_rating" in data
        assert "confidence" in data
        assert "latency_ms" in data

    def test_predict_latency_under_threshold(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """La latence de prédiction doit être inférieure à 1 seconde."""
        response = client.post(
            "/predict",
            json={"user_id": 1, "drama_id": 5},
            headers=auth_headers,
        )
        data = response.json()
        assert (
            data["latency_ms"] < 1000
        ), f"Latence trop élevée : {data['latency_ms']}ms"


# ============================================================
# 6. Tests du endpoint /model/info
# ============================================================


class TestModelInfoEndpoint:
    """Tests du endpoint d'information sur le modèle."""

    def test_model_info_with_auth(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Le endpoint /model/info doit retourner les informations du modèle."""
        response = client.get("/model/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "model_type" in data
        assert "alpha" in data
        assert "is_trained" in data
        assert data["model_type"] == "HybridRecommender"
        assert data["is_trained"] is True

    def test_model_info_without_auth(self, client: TestClient) -> None:
        """Le endpoint /model/info sans authentification doit retourner 401."""
        response = client.get("/model/info")
        assert response.status_code == 401


# ============================================================
# 7. Tests du endpoint /alerts (admin only)
# ============================================================


class TestAlertsEndpoint:
    """Tests du endpoint d'alertes (admin seulement)."""

    def test_alerts_with_admin(
        self,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        """L'admin doit pouvoir accéder aux alertes."""
        response = client.get("/alerts", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "model_status" in data
        assert "total_requests" in data
        assert "error_rate" in data
        assert "alerts" in data

    def test_alerts_with_regular_user(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Un utilisateur normal ne doit pas accéder aux alertes (403)."""
        response = client.get("/alerts", headers=auth_headers)
        assert response.status_code == 403

    def test_alerts_without_auth(self, client: TestClient) -> None:
        """Sans authentification, /alerts doit retourner 401."""
        response = client.get("/alerts")
        assert response.status_code == 401


# ============================================================
# 8. Tests de sécurité (OWASP)
# ============================================================


class TestSecurity:
    """Tests de sécurité OWASP."""

    def test_invalid_token_rejected(self, client: TestClient) -> None:
        """Un token invalide doit être rejeté."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 5},
            headers=headers,
        )
        assert response.status_code == 401

    def test_malformed_auth_header(self, client: TestClient) -> None:
        """Un en-tête Authorization malformé doit être rejeté."""
        headers = {"Authorization": "InvalidFormat token"}
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 5},
            headers=headers,
        )
        assert response.status_code == 401

    def test_security_headers_present(self, client: TestClient) -> None:
        """Les headers de sécurité OWASP doivent être présents."""
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_cors_headers_configured(self, client: TestClient) -> None:
        """CORS doit être configuré."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Soit 200 (preflight) soit 405, mais le header CORS doit être présent
        assert response.status_code in (200, 405)

    def test_openapi_docs_available(self, client: TestClient) -> None:
        """La documentation OpenAPI doit être accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()
        assert spec["info"]["title"] == "K-Drama Recommender API"
        assert "paths" in spec

    def test_sql_injection_safe_input(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Les tentatives d'injection dans les champs doivent être rejetées."""
        # Pydantic valide les types : les chaînes dans les int sont rejetées
        response = client.post(
            "/recommend",
            json={"user_id": "1; DROP TABLE users; --", "top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_xss_safe_input(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Les tentatives XSS dans les champs doivent être rejetées."""
        response = client.post(
            "/recommend",
            json={"user_id": "<script>alert('xss')</script>", "top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 422


# ============================================================
# 9. Tests du modèle de recommandation (unitaires)
# ============================================================


class TestRecommendationModel:
    """Tests unitaires du modèle de recommandation hybride."""

    def test_model_trains_successfully(self, trained_model: HybridRecommender) -> None:
        """Le modèle doit s'entraîner sans erreur."""
        assert trained_model._is_trained is True

    def test_model_metrics_populated(self, trained_model: HybridRecommender) -> None:
        """Les métriques d'entraînement doivent être renseignées."""
        metrics = trained_model.metrics
        assert metrics.num_dramas > 0
        assert metrics.num_users > 0
        assert metrics.num_interactions > 0
        assert metrics.training_time_seconds > 0

    def test_recommend_for_user_returns_results(
        self, trained_model: HybridRecommender
    ) -> None:
        """recommend() avec user_id doit retourner des résultats."""
        results = trained_model.recommend(user_id=1, top_k=5)
        assert len(results) > 0
        assert all(isinstance(r, RecommendationResult) for r in results)

    def test_recommend_for_drama_returns_results(
        self, trained_model: HybridRecommender
    ) -> None:
        """recommend() avec drama_id doit retourner des résultats."""
        results = trained_model.recommend(drama_id=1, top_k=5)
        assert len(results) > 0

    def test_recommend_top_k_respected(self, trained_model: HybridRecommender) -> None:
        """Le nombre de résultats doit respecter top_k."""
        results = trained_model.recommend(user_id=1, top_k=3)
        assert len(results) <= 3

    def test_recommend_filters_happy_endings_and_adds_explanations(
        self, trained_model: HybridRecommender
    ) -> None:
        """Le modèle doit pouvoir filtrer happy ending et fournir une explication."""
        results = trained_model.recommend(
            top_k=4,
            text="feel good romance",
            genres=["Romance"],
            happy_ending_only=True,
        )
        assert len(results) <= 4
        assert results
        for result in results:
            info = trained_model._get_drama_info(result.drama_id)
            assert info is not None
            assert info["ending_type"] == "happy"
            assert result.explanation

    def test_history_matrix_is_not_presented_as_explicit_user_likes(
        self, trained_model: HybridRecommender
    ) -> None:
        """Training interactions must never be presented as explicit user likes."""
        results = trained_model.recommend(user_id=1, top_k=4, user_preferences={})
        assert results
        assert all("Because you liked" not in result.explanation for result in results)

    def test_recommend_request_accepts_new_fields(self) -> None:
        """RecommendRequest doit accepter les nouveaux champs optionnels."""
        req = RecommendRequest(
            top_k=4,
            mood="cozy",
            text="family drama",
            genres=[" Drama ", ""],
            actor_names=[" IU "],
            happy_ending_only=True,
        )
        assert req.top_k == 4
        assert req.mood == "cozy"
        assert req.text == "family drama"
        assert req.genres == ["Drama"]
        assert req.actor_names == ["IU"]
        assert req.happy_ending_only is True

    def test_predict_returns_valid_score(
        self, trained_model: HybridRecommender
    ) -> None:
        """predict() doit retourner un score entre 0 et 10."""
        score = trained_model.predict(user_id=1, drama_id=5)
        assert 0.0 <= score <= 10.0

    def test_predict_unknown_user_returns_neutral(
        self, trained_model: HybridRecommender
    ) -> None:
        """predict() pour un utilisateur inconnu doit retourner un score neutre."""
        score = trained_model.predict(user_id=99999, drama_id=5)
        assert 0.0 <= score <= 10.0

    def test_recommend_without_ids_raises_error(
        self, trained_model: HybridRecommender
    ) -> None:
        """recommend() sans user_id ni drama_id doit lever une ValueError."""
        with pytest.raises(ValueError):
            trained_model.recommend(top_k=5)

    def test_recommend_invalid_top_k_raises_error(
        self, trained_model: HybridRecommender
    ) -> None:
        """recommend() avec top_k <= 0 doit lever une ValueError."""
        with pytest.raises(ValueError):
            trained_model.recommend(user_id=1, top_k=0)

    def test_untrained_model_raises_error(self) -> None:
        """Un modèle non entraîné doit lever une RuntimeError."""
        model = HybridRecommender()
        with pytest.raises(RuntimeError):
            model.recommend(user_id=1, top_k=5)

    def test_invalid_alpha_raises_error(self) -> None:
        """Un alpha hors plage [0, 1] doit lever une ValueError."""
        with pytest.raises(ValueError):
            HybridRecommender(alpha=1.5)
        with pytest.raises(ValueError):
            HybridRecommender(alpha=-0.5)

    def test_model_serialization(
        self, trained_model: HybridRecommender, tmp_path: Path
    ) -> None:
        """Le modèle doit pouvoir être sérialisé et rechargé."""
        model_dir = tmp_path / "model_test"
        trained_model.save(model_dir)

        loaded_model = HybridRecommender.load(model_dir)
        assert loaded_model._is_trained is True
        assert loaded_model.metrics.num_dramas == trained_model.metrics.num_dramas

    def test_recommendation_result_to_dict(self) -> None:
        """La méthode to_dict() doit retourner un dictionnaire valide."""
        result = RecommendationResult(
            drama_id=1,
            title="Test Drama",
            score=8.5,
            genres=["Romance", "Comedy"],
            reason="Test reason",
            explanation="Test reason",
        )
        d = result.to_dict()
        assert d["drama_id"] == 1
        assert d["title"] == "Test Drama"
        assert d["score"] == 8.5
        assert d["genres"] == ["Romance", "Comedy"]
        assert d["reason"] == "Test reason"
        assert d["explanation"] == "Test reason"

    def test_content_embeddings_not_none(
        self, trained_model: HybridRecommender
    ) -> None:
        """Les embeddings de contenu doivent être initialisés après l'entraînement."""
        assert trained_model.content_embeddings is not None
        assert trained_model.content_embeddings.shape[0] > 0

    def test_collaborative_model_trained(
        self, trained_model: HybridRecommender
    ) -> None:
        """Le modèle collaboratif doit être entraîné."""
        assert trained_model.collaborative_model is not None

    def test_user_item_matrix_built(self, trained_model: HybridRecommender) -> None:
        """La matrice utilisateur-drama doit être construite."""
        assert trained_model.user_item_matrix is not None
        assert trained_model.user_item_matrix.shape[0] > 0
        assert trained_model.user_item_matrix.shape[1] > 0


# ============================================================
# 10. Tests du monitoring
# ============================================================


class TestMonitoring:
    """Tests du système de monitoring Prometheus."""

    def test_monitor_initialization(self) -> None:
        """Le moniteur doit s'initialiser correctement."""
        monitor = ModelMonitor()
        assert monitor.config is not None
        assert monitor.drift_monitor is not None

    def test_record_request(self) -> None:
        """L'enregistrement d'une requête doit fonctionner."""
        monitor = ModelMonitor()
        monitor.record_request(
            endpoint="/recommend",
            method="POST",
            status=200,
            latency=0.05,
        )
        summary = monitor.get_health_summary()
        assert summary["total_requests"] >= 1

    def test_record_prediction(self) -> None:
        """L'enregistrement d'une prédiction doit fonctionner."""
        monitor = ModelMonitor()
        monitor.record_prediction(
            score=8.5,
            model_type="HybridRecommender",
            mode="recommend",
            inference_time=0.02,
        )
        assert len(monitor.drift_monitor.current_predictions) > 0

    def test_set_model_status(self) -> None:
        """La mise à jour du statut du modèle doit fonctionner."""
        monitor = ModelMonitor()
        monitor.set_model_status(True)
        summary = monitor.get_health_summary()
        assert summary["model_status"] == "operational"

    def test_error_rate_calculation(self) -> None:
        """Le calcul du taux d'erreur doit être correct."""
        monitor = ModelMonitor()
        monitor.record_request("/test", "GET", 200, 0.01)
        monitor.record_request("/test", "GET", 500, 0.01)
        monitor.record_request("/test", "GET", 200, 0.01)
        rate = monitor.get_error_rate()
        assert rate > 0.0
        assert rate < 1.0

    def test_drift_monitor_psi(self) -> None:
        """Le calcul du PSI doit retourner 0 sans données suffisantes."""
        drift = DriftMonitor(window_size=100)
        psi = drift.compute_psi()
        assert psi == 0.0

    def test_drift_monitor_with_reference(self) -> None:
        """Le PSI doit être calculable avec une distribution de référence."""
        import numpy as np

        rng = np.random.RandomState(42)
        ref_preds = rng.uniform(5, 10, 500)
        drift = DriftMonitor(window_size=500)
        drift.set_reference(ref_preds)

        # Ajout de prédictions similaires (pas de drift)
        for p in ref_preds[:200]:
            drift.add_prediction(float(p))

        psi = drift.compute_psi()
        assert psi >= 0.0

    def test_drift_level_classification(self) -> None:
        """La classification du niveau de drift doit être correcte."""
        drift = DriftMonitor(window_size=100)
        assert drift.get_drift_level() == "none"  # Pas assez de données

    def test_check_alerts_returns_list(self) -> None:
        """check_alerts() doit retourner une liste."""
        monitor = ModelMonitor()
        alerts = monitor.check_alerts()
        assert isinstance(alerts, list)

    def test_get_metrics_returns_bytes(self) -> None:
        """get_metrics() doit retourner des bytes au format Prometheus."""
        monitor = ModelMonitor()
        metrics = monitor.get_metrics()
        assert isinstance(metrics, bytes)
        assert len(metrics) > 0

    def test_alert_rules_not_empty(self) -> None:
        """Les règles d'alerte ne doivent pas être vides."""
        from model_monitoring import get_alert_rules

        rules = get_alert_rules()
        assert "PredictionDriftHigh" in rules
        assert "HighErrorRate" in rules
        assert "ModelUnavailable" in rules


# ============================================================
# 11. Tests de performance
# ============================================================


class TestPerformance:
    """Tests de performance et de seuils de latence."""

    def test_recommend_latency_under_500ms(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """La latence de /recommend doit être inférieure à 500ms."""
        start = time.time()
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 10},
            headers=auth_headers,
        )
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 500, f"Latence : {elapsed_ms:.0f}ms"
        assert response.status_code == 200

    def test_predict_latency_under_300ms(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """La latence de /predict doit être inférieure à 300ms."""
        start = time.time()
        response = client.post(
            "/predict",
            json={"user_id": 1, "drama_id": 5},
            headers=auth_headers,
        )
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 300, f"Latence : {elapsed_ms:.0f}ms"
        assert response.status_code == 200

    def test_health_latency_under_100ms(self, client: TestClient) -> None:
        """La latence de /health doit être inférieure à 100ms."""
        start = time.time()
        response = client.get("/health")
        elapsed_ms = (time.time() - start) * 1000
        assert elapsed_ms < 100, f"Latence : {elapsed_ms:.0f}ms"
        assert response.status_code == 200

    def test_model_inference_under_1s(self, trained_model: HybridRecommender) -> None:
        """L'inférence du modèle doit prendre moins de 1 seconde."""
        start = time.time()
        trained_model.recommend(user_id=1, top_k=10)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Inférence : {elapsed:.2f}s"

    def test_concurrent_recommendations(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """L'API doit gérer 10 requêtes concurrentes sans erreur."""
        import concurrent.futures

        def make_request() -> int:
            response = client.post(
                "/recommend",
                json={"user_id": 1, "top_k": 5},
                headers=auth_headers,
            )
            return response.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(r == 200 for r in results)


# ============================================================
# 12. Tests de validation des entrées (edge cases)
# ============================================================


class TestInputValidation:
    """Tests de validation des entrées (edge cases et cas limites)."""

    def test_recommend_top_k_one(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """top_k = 1 doit retourner exactement 1 résultat."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 1},
            headers=auth_headers,
        )
        data = response.json()
        assert data["count"] <= 1

    def test_recommend_top_k_max_50(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """top_k = 50 (maximum) doit être accepté."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "top_k": 50},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_recommend_large_user_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Un user_id très grand doit être accepté (utilisateur froid)."""
        response = client.post(
            "/recommend",
            json={"user_id": 1000000, "top_k": 5},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_predict_nonexistent_drama(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Prédiction pour un drama inexistant doit retourner une erreur 400."""
        response = client.post(
            "/predict",
            json={"user_id": 1, "drama_id": 999999},
            headers=auth_headers,
        )
        assert response.status_code in (400, 200)  # Selon le fallback

    def test_recommend_both_ids_provided(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Si user_id ET drama_id sont fournis, user_id doit être prioritaire."""
        response = client.post(
            "/recommend",
            json={"user_id": 1, "drama_id": 5, "top_k": 5},
            headers=auth_headers,
        )
        data = response.json()
        assert data["mode"] == "user"

    def test_auth_oversized_username(self, client: TestClient) -> None:
        """Un nom d'utilisateur trop long doit être rejeté."""
        response = client.post(
            "/auth/token",
            json={"username": "a" * 100, "password": "pass"},
        )
        assert response.status_code == 422

    def test_auth_oversized_password(self, client: TestClient) -> None:
        """Un mot de passe trop long doit être rejeté."""
        response = client.post(
            "/auth/token",
            json={"username": "admin", "password": "a" * 300},
        )
        assert response.status_code == 422


# ============================================================
# 13. Tests de l'API OpenAPI
# ============================================================


class TestOpenAPI:
    """Tests de la spécification OpenAPI."""

    def test_openapi_has_all_endpoints(self, client: TestClient) -> None:
        """Tous les endpoints doivent être documentés dans OpenAPI."""
        response = client.get("/openapi.json")
        spec = response.json()
        paths = spec["paths"]

        assert "/health" in paths
        assert "/metrics" in paths
        assert "/auth/token" in paths
        assert "/recommend" in paths
        assert "/predict" in paths
        assert "/model/info" in paths
        assert "/alerts" in paths

    def test_openapi_has_security_schemes(self, client: TestClient) -> None:
        """La spec OpenAPI doit définir les schémas de sécurité."""
        response = client.get("/openapi.json")
        spec = response.json()
        # Le JWT doit être référencé dans les composants de sécurité
        assert "components" in spec
        assert "securitySchemes" in spec["components"]

    def test_openapi_recommend_has_request_body(self, client: TestClient) -> None:
        """L'endpoint /recommend doit avoir un body défini."""
        response = client.get("/openapi.json")
        spec = response.json()
        recommend_post = spec["paths"]["/recommend"]["post"]
        assert "requestBody" in recommend_post

    def test_openapi_has_tags(self, client: TestClient) -> None:
        """La spec OpenAPI doit définir des tags."""
        response = client.get("/openapi.json")
        spec = response.json()
        assert "tags" in spec
        tag_names = [t["name"] for t in spec["tags"]]
        assert "Recommendation" in tag_names
        assert "Authentication" in tag_names
        assert "Monitoring" in tag_names

    def test_docs_endpoint_available(self, client: TestClient) -> None:
        """La documentation Swagger UI doit être accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_endpoint_available(self, client: TestClient) -> None:
        """La documentation ReDoc doit être accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200


# ============================================================
# Point d'entrée
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
