from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ajout du répertoire src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import data_loader  # noqa: E402


class _FakeResult:
    def __init__(self, rows: list[tuple], columns: list[str]) -> None:
        self._rows = rows
        self._columns = columns

    def fetchall(self) -> list[tuple]:
        return self._rows

    def keys(self) -> list[str]:
        return self._columns


class _FakeConnection:
    def __init__(self, result: _FakeResult | None = None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def execute(self, _query):  # type: ignore[no-untyped-def]
        if self._exc is not None:
            raise self._exc
        assert self._result is not None
        return self._result


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection
        self.disposed = False

    def connect(self) -> _FakeConnection:
        return self._connection

    def dispose(self) -> None:
        self.disposed = True


def test_get_database_url_prefers_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://supabase")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fallback")
    assert data_loader._get_database_url() == "postgresql://supabase"


def test_get_database_url_falls_back_to_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fallback")
    assert data_loader._get_database_url() == "postgresql://fallback"


def test_get_database_url_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Database connection is not configured"):
        data_loader._get_database_url()


def test_load_dramas_from_etape1_success(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        (1, "Drama A", None, None, 8.5, 100, "2020-01-01", "SBS", "Actor A", "tag1"),
        (2, "Drama B", "Synopsis B", "Action", 7.9, 80, "2021-01-01", "tvN", "Actor B", "tag2"),
    ]
    cols = [
        "drama_id",
        "title",
        "synopsis",
        "genres",
        "note_moyenne",
        "nb_votes",
        "date_diffusion",
        "reseaux_diffusion",
        "acteurs",
        "tags",
    ]
    fake_engine = _FakeEngine(_FakeConnection(result=_FakeResult(rows, cols)))
    monkeypatch.setattr(data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine)

    df = data_loader.load_dramas_from_etape1(db_url="postgresql://fake")

    assert len(df) == 2
    assert list(df.columns) == cols
    assert df.loc[0, "synopsis"] == ""
    assert df.loc[0, "genres"] == ""
    assert fake_engine.disposed is True


def test_load_dramas_from_etape1_raises_on_query_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_engine = _FakeEngine(_FakeConnection(exc=Exception("db down")))
    monkeypatch.setattr(data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine)

    with pytest.raises(RuntimeError, match="Error reading the kdramas table"):
        data_loader.load_dramas_from_etape1(db_url="postgresql://fake")

    assert fake_engine.disposed is True


def test_load_dramas_from_etape1_raises_on_empty_table(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_result = _FakeResult([], ["drama_id", "title", "synopsis", "genres", "note_moyenne"])
    fake_engine = _FakeEngine(_FakeConnection(result=fake_result))
    monkeypatch.setattr(data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine)

    with pytest.raises(RuntimeError, match="kdramas table is empty"):
        data_loader.load_dramas_from_etape1(db_url="postgresql://fake")


def test_generate_interactions_requires_note_moyenne_column() -> None:
    dramas_df = pd.DataFrame({"drama_id": [1, 2], "title": ["A", "B"]})
    with pytest.raises(ValueError, match="note_moyenne"):
        data_loader.generate_interactions_from_catalog(dramas_df)


def test_generate_interactions_output_shape_and_bounds() -> None:
    dramas_df = pd.DataFrame(
        {
            "drama_id": [1, 2, 3, 4],
            "note_moyenne": [8.0, 7.5, None, 9.2],
        }
    )

    interactions_df = data_loader.generate_interactions_from_catalog(
        dramas_df,
        num_users=10,
        avg_interactions_per_user=3,
        noise_std=0.5,
        random_state=42,
    )

    assert not interactions_df.empty
    assert set(interactions_df.columns) == {"user_id", "drama_id", "rating"}
    assert interactions_df["user_id"].nunique() == 10
    assert interactions_df["rating"].between(1.0, 10.0).all()
    assert interactions_df.duplicated(subset=["user_id", "drama_id"]).sum() == 0


def test_load_real_data_orchestration(monkeypatch: pytest.MonkeyPatch) -> None:
    dramas_df = pd.DataFrame({"drama_id": [1], "note_moyenne": [8.0]})
    interactions_df = pd.DataFrame({"user_id": [1], "drama_id": [1], "rating": [8.2]})

    called: dict[str, object] = {}

    def fake_load(db_url: str | None = None) -> pd.DataFrame:
        called["db_url"] = db_url
        return dramas_df

    def fake_generate(
        input_df: pd.DataFrame,
        num_users: int = 50,
        avg_interactions_per_user: int = 8,
        noise_std: float = 1.0,
        random_state: int = 42,
    ) -> pd.DataFrame:
        called["input_df_is_same"] = input_df is dramas_df
        called["num_users"] = num_users
        called["avg"] = avg_interactions_per_user
        called["noise_std"] = noise_std
        called["random_state"] = random_state
        return interactions_df

    monkeypatch.setattr(data_loader, "load_dramas_from_etape1", fake_load)
    monkeypatch.setattr(data_loader, "generate_interactions_from_catalog", fake_generate)

    got_dramas, got_interactions = data_loader.load_real_data(
        db_url="postgresql://fake",
        num_users=7,
        avg_interactions_per_user=4,
    )

    assert got_dramas is dramas_df
    assert got_interactions is interactions_df
    assert called["db_url"] == "postgresql://fake"
    assert called["input_df_is_same"] is True
    assert called["num_users"] == 7
    assert called["avg"] == 4
