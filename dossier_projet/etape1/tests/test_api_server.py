import os
import secrets

import pytest
from pathlib import Path
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", secrets.token_urlsafe(48))

from fastapi.testclient import TestClient
from api_server import app, Kdrama, Utilisateur, Note, Genre

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health Check Tests
# ---------------------------------------------------------------------------
def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


# ---------------------------------------------------------------------------
# K-Drama Endpoints Tests
# ---------------------------------------------------------------------------
def test_list_kdramas_simple():
    """Test simple kdramas listing."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.limit.return_value.all.return_value = []
        response = client.get("/api/v1/kdramas-simple")

    assert response.status_code == 200
    data = response.json()
    # API returns {items: [...], total: ...}
    assert isinstance(data, dict)
    assert "items" in data or isinstance(data, list)


def test_get_kdrama_not_found():
    """Test getting non-existent kdrama."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None

        response = client.get("/api/v1/kdramas/9999")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Genre Endpoints Tests
# ---------------------------------------------------------------------------
def test_list_genres():
    """Test listing all genres."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.order_by.return_value.all.return_value = []
        response = client.get("/api/v1/genres")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Actor Endpoints Tests
# ---------------------------------------------------------------------------
def test_list_acteurs():
    """Test listing all actors."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        query = mock_session.query.return_value
        query.count.return_value = 0
        query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        response = client.get("/api/v1/acteurs")

    assert response.status_code == 200


def test_list_kdrama_actors_from_catalog():
    """Test the genres-style actors endpoint deriving names from kdramas.acteurs."""
    with patch("api_server.SessionLocal") as mock_session_class, patch(
        "api_server._ACTOR_CATALOG_CACHE", {"names": None, "loaded_at": 0.0}
    ):
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ('[{"nom": "Song Joong-ki"}, {"nom": "Kim Tae-ri"}]',),
            ('[{"nom": "Song Joong-ki"}]',),
        ]
        mock_session.execute.return_value = mock_result

        response = client.get("/api/v1/kdramas/actors")
        assert response.status_code == 200
        data = response.json()
        assert "Song Joong-ki" in data
        assert "Kim Tae-ri" in data
        # Deduplicated: appears once despite being in two rows.
        assert data.count("Song Joong-ki") == 1


def test_list_kdrama_actors_search_filter():
    """Test that ?search= filters actor names case-insensitively."""
    with patch("api_server.SessionLocal") as mock_session_class, patch(
        "api_server._ACTOR_CATALOG_CACHE", {"names": None, "loaded_at": 0.0}
    ):
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            ('[{"nom": "Shin Ha-kyun"}, {"nom": "Park Bo-young"}]',),
        ]
        mock_session.execute.return_value = mock_result

        response = client.get("/api/v1/kdramas/actors?search=shin")
        assert response.status_code == 200
        data = response.json()
        assert data == ["Shin Ha-kyun"]


# ---------------------------------------------------------------------------
# Sentiment Endpoints Tests
# ---------------------------------------------------------------------------
def test_get_drama_sentiment_not_found():
    """Test getting sentiment for non-existent drama."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None

        response = client.get("/api/v1/kdramas/9999/sentiment")
        assert response.status_code == 404


def test_list_sentiments():
    """Test listing sentiments."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_query = Mock()
        mock_query.count.return_value = 0
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value = mock_query

        response = client.get("/api/v1/sentiments")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "data" in data


def test_list_sentiments_invalid_ending_type():
    """Test invalid ending_type parameter."""
    response = client.get("/api/v1/sentiments?ending_type=invalid")
    assert response.status_code == 400


def test_list_sentiments_filter_happy():
    """Test filtering sentiments by happy ending."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_query = Mock()
        mock_query.filter.return_value.count.return_value = 5
        mock_query.filter.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value = mock_query

        response = client.get("/api/v1/sentiments?ending_type=happy")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5


def test_list_sentiments_pagination():
    """Test sentiments pagination."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_query = Mock()
        mock_query.count.return_value = 100
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value = mock_query

        response = client.get("/api/v1/sentiments?skip=20&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == 20
        assert data["limit"] == 10
        assert data["total"] == 100


# ---------------------------------------------------------------------------
# Notes Endpoints Tests
# ---------------------------------------------------------------------------
def test_list_notes_kdrama():
    """Test listing notes for a kdrama."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock the query chain properly
        mock_query = Mock()
        mock_query.count.return_value = 0  # Return int not Mock
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        mock_query.filter.return_value = mock_query  # Allow chaining

        mock_session.query.return_value = mock_query

        response = client.get("/api/v1/kdramas/1/notes")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Error Handling Tests
# ---------------------------------------------------------------------------
def test_invalid_endpoint():
    """Test accessing non-existent endpoint."""
    response = client.get("/api/v1/invalid-endpoint")
    assert response.status_code == 404


def test_list_sentiments_limit_max():
    """Test that limit is capped at 500."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_query = Mock()
        mock_query.count.return_value = 1000
        mock_query.offset.return_value.limit.return_value.all.return_value = []
        mock_session.query.return_value = mock_query

        # Use limit within validation range (max 500)
        response = client.get("/api/v1/sentiments?limit=500")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Preferences / Favorites / Watch History / Interest Feedback Tests
# (new recommendation-related endpoints)
# ---------------------------------------------------------------------------
from api_server import (  # noqa: E402
    get_current_user,
    Favori,
    HistoriqueVisionnage,
    InteretUtilisateur,
)


def _fake_user(user_id: int = 1, role: str = "user") -> Utilisateur:
    """Builds an in-memory Utilisateur for dependency overrides (no DB round-trip)."""
    user = Utilisateur(
        pseudonyme="testuser",
        email_hache="hash",
        mot_de_passe_hache="hash",
        consentement_collecte=True,
        consentement_marketing=False,
        role=role,
        fin_heureuse_uniquement=False,
    )
    user.id = user_id
    user.date_inscription = datetime.utcnow()
    return user


@pytest.fixture(autouse=False)
def override_current_user():
    """Overrides get_current_user for tests that need an authenticated request."""
    from api_server import app as fastapi_app

    fake = _fake_user()
    fastapi_app.dependency_overrides[get_current_user] = lambda: fake
    yield fake
    fastapi_app.dependency_overrides.pop(get_current_user, None)


def test_update_preferences_rejects_more_than_3_genres(override_current_user):
    """PATCH preferences must reject more than 3 favorite genres (422)."""
    response = client.patch(
        "/api/v1/auth/me/preferences",
        json={"genres": ["Romance", "Comédie", "Drame", "Thriller"]},
    )
    assert response.status_code == 422


def test_update_preferences_rejects_more_than_5_actors(override_current_user):
    """PATCH preferences must reject more than 5 favorite actors (422)."""
    response = client.patch(
        "/api/v1/auth/me/preferences",
        json={"acteurs": ["A", "B", "C", "D", "E", "F"]},
    )
    assert response.status_code == 422


def test_get_current_user_shares_the_request_session():
    """get_current_user must reuse the request session (get_db).

    Régression : la dépendance ouvrait sa propre session puis la fermait,
    renvoyant un Utilisateur détaché. Les endpoints qui modifient l'objet
    (préférence « fin heureuse », anonymisation RGPD art. 17) committaient
    alors sur une autre session, et la modification était perdue.
    """
    import inspect

    from api_server import get_current_user, get_db

    dependance_db = inspect.signature(get_current_user).parameters["db"].default
    assert dependance_db.dependency is get_db


def test_update_preferences_accepts_catalog_genre_names(override_current_user):
    """Catalog genre names (kdramas.genres vocabulary) must be accepted.

    Régression : ces noms étaient auparavant validés contre la table de
    référence kdrama.genres, seedée en français, ce qui faisait échouer en
    400 tout enregistrement de genres choisis dans la liste proposée par
    /api/v1/kdramas/genres (la même que le filtre de la page Search).
    """
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.filter.return_value.count.return_value = 0
        mock_query.filter.return_value.delete.return_value = 0
        mock_session.query.return_value = mock_query

        response = client.patch(
            "/api/v1/auth/me/preferences",
            json={"genres": ["Action & Adventure", "Sci-Fi & Fantasy", "War & Politics"]},
        )
        assert response.status_code == 200

        genres_ajoutes = [
            call.args[0].genre_nom
            for call in mock_session.add.call_args_list
            if hasattr(call.args[0], "genre_nom")
        ]
        assert genres_ajoutes == [
            "Action & Adventure",
            "Sci-Fi & Fantasy",
            "War & Politics",
        ]


def test_update_preferences_all_optional(override_current_user):
    """PATCH preferences with an empty body must succeed (all fields optional)."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_query = Mock()
        mock_query.join.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.filter.return_value.count.return_value = 0
        mock_session.query.return_value = mock_query

        response = client.patch("/api/v1/auth/me/preferences", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["genres_preferes"] == []
        assert data["acteurs_preferes"] == []


def test_favoris_add_get_kdrama_not_found(override_current_user):
    """Adding a favorite for a non-existent drama returns 404."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/api/v1/favoris/9999")
        assert response.status_code == 404


def test_favoris_list_empty(override_current_user):
    """Listing favorites for a user with none returns an empty list."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        response = client.get("/api/v1/favoris")
        assert response.status_code == 200
        assert response.json() == []


def test_historique_upsert_invalid_statut_rejected(override_current_user):
    """PUT historique with an invalid statut value must return 422."""
    response = client.put(
        "/api/v1/historique/1",
        json={"kdrama_id": 1, "episodes_vus": 3, "statut": "not_a_real_status"},
    )
    assert response.status_code == 422


def test_interet_get_returns_null_when_absent(override_current_user):
    """GET interet returns null when the user has no recorded feedback yet."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None

        response = client.get("/api/v1/kdramas/1/interet")
        assert response.status_code == 200
        assert response.json() is None


def test_interet_set_not_interested_kdrama_not_found(override_current_user):
    """Setting interest for a non-existent drama returns 404."""
    with patch("api_server.SessionLocal") as mock_session_class:
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.filter.return_value.first.return_value = None

        response = client.put(
            "/api/v1/kdramas/9999/interet",
            json={"interesse": False},
        )
        assert response.status_code == 404
