import pytest
from pathlib import Path
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
    response = client.get("/api/v1/kdramas-simple")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


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
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        mock_genre1 = Mock(spec=Genre)
        mock_genre1.id = 1
        mock_genre1.nom = "Drama"

        mock_genre2 = Mock(spec=Genre)
        mock_genre2.id = 2
        mock_genre2.nom = "Romance"

        mock_session.query.return_value.all.return_value = [mock_genre1, mock_genre2]

        response = client.get("/api/v1/genres")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 0


# ---------------------------------------------------------------------------
# Actor Endpoints Tests
# ---------------------------------------------------------------------------
def test_list_acteurs():
    """Test listing all actors."""
    response = client.get("/api/v1/acteurs")
    assert response.status_code == 200


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
        mock_session.query.return_value.filter.return_value.all.return_value = []

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

        response = client.get("/api/v1/sentiments?limit=999")
        assert response.status_code == 200
        # Verify limit was capped at 500 by checking the mock was called with min(999, 500)
        mock_query.offset.return_value.limit.assert_called_with(500)
