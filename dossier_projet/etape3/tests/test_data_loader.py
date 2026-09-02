from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

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
    def __init__(
        self,
        result: _FakeResult | None = None,
        exc: Exception | None = None,
        query_results: dict[str, _FakeResult] | None = None,
    ) -> None:
        self._result = result
        self._exc = exc
        self._query_results = query_results or {}

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None

    def execute(self, query, *args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        if self._exc is not None:
            raise self._exc
        sql = str(query).lower()
        for marker, result in self._query_results.items():
            if marker.lower() in sql:
                return result
        if self._result is not None:
            return self._result
        raise AssertionError(f"No fake result configured for query: {sql}")


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


def test_get_database_url_falls_back_to_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        (
            101,
            "Drama A",
            None,
            None,
            8.5,
            100,
            "2020-01-01",
            16,
            1,
            "SBS",
            "Actor A",
            "tag1",
            "poster-a",
            "happy",
            0.7,
            "comments",
            "consensus",
            "summary",
            "Actor A",
        ),
        (
            102,
            "Drama B",
            "Synopsis B",
            "Action",
            7.9,
            80,
            "2021-01-01",
            12,
            1,
            "tvN",
            "Actor B",
            "tag2",
            "poster-b",
            "sad",
            -0.2,
            "",
            "",
            "",
            "Actor B",
        ),
    ]
    cols = [
        "drama_id",
        "title",
        "synopsis",
        "genres",
        "note_moyenne",
        "nb_votes",
        "date_diffusion",
        "nb_episodes",
        "nb_saisons",
        "reseaux_diffusion",
        "acteurs",
        "tags",
        "poster",
        "ending_type",
        "sentiment_score",
        "top_comments",
        "viewer_consensus",
        "sentiment_summary",
        "principal_actors",
    ]
    fake_engine = _FakeEngine(_FakeConnection(result=_FakeResult(rows, cols)))
    monkeypatch.setattr(
        data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine
    )

    df = data_loader.load_dramas_from_etape1(db_url="postgresql://fake")

    assert len(df) == 2
    assert set(cols).issubset(df.columns)
    assert df.loc[0, "synopsis"] == ""
    assert df.loc[0, "genres"] == ""
    assert df.loc[0, "ending_type"] == "happy"
    assert df.loc[0, "principal_actors"] == "Actor A"
    assert fake_engine.disposed is True


def test_load_dramas_from_etape1_raises_on_query_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = _FakeEngine(_FakeConnection(exc=Exception("db down")))
    monkeypatch.setattr(
        data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine
    )

    with pytest.raises(RuntimeError, match="Error reading the kdramas table"):
        data_loader.load_dramas_from_etape1(db_url="postgresql://fake")

    assert fake_engine.disposed is True


def test_load_dramas_from_etape1_raises_on_empty_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_result = _FakeResult([], ["drama_id", "title", "synopsis", "genres", "note_moyenne"])
    fake_engine = _FakeEngine(_FakeConnection(result=fake_result))
    monkeypatch.setattr(
        data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine
    )

    with pytest.raises(RuntimeError, match="kdramas table is empty"):
        data_loader.load_dramas_from_etape1(db_url="postgresql://fake")


def test_load_dramas_from_etape1_uses_snapshot_when_flag_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_df = pd.DataFrame(
        {
            "drama_id": [1, 2],
            "title": ["Snapshot A", "Snapshot B"],
            "synopsis": ["a", "b"],
            "genres": ["Drama", "Comedy"],
            "note_moyenne": [7.1, 8.3],
        }
    )

    monkeypatch.setenv("USE_LOCAL_DATA_SNAPSHOT", "true")
    monkeypatch.setattr(
        data_loader,
        "_load_dramas_from_snapshot",
        lambda *_args, **_kwargs: snapshot_df,
    )

    def _unexpected_engine(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("create_engine should not be called in snapshot mode")

    monkeypatch.setattr(data_loader, "create_engine", _unexpected_engine)

    got = data_loader.load_dramas_from_etape1(db_url="postgresql://fake")
    assert got is snapshot_df


def test_load_dramas_from_etape1_fallback_on_db_error_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_df = pd.DataFrame(
        {
            "drama_id": [1],
            "title": ["Snapshot"],
            "synopsis": ["syn"],
            "genres": ["Drama"],
            "note_moyenne": [8.0],
        }
    )

    fake_engine = _FakeEngine(_FakeConnection(exc=Exception("db down")))
    monkeypatch.setenv("FALLBACK_TO_LOCAL_ON_DB_ERROR", "true")
    monkeypatch.setattr(
        data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine
    )
    monkeypatch.setattr(
        data_loader,
        "_load_dramas_from_snapshot",
        lambda *_args, **_kwargs: snapshot_df,
    )

    got = data_loader.load_dramas_from_etape1(db_url="postgresql://fake")
    assert got is snapshot_df
    assert fake_engine.disposed is True


def test_load_dramas_from_snapshot_uses_embedded_when_missing_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedded_df = pd.DataFrame(
        {
            "drama_id": [1, 2],
            "title": ["Embedded A", "Embedded B"],
            "synopsis": ["", ""],
            "genres": ["Drama", "Comedy"],
            "note_moyenne": [8.0, 7.5],
        }
    )
    missing_path = Path("C:/definitely/missing/snapshot.csv")

    monkeypatch.setattr(data_loader, "_load_embedded_catalog", lambda: embedded_df)

    got = data_loader._load_dramas_from_snapshot(missing_path)
    assert got is embedded_df


def test_load_dramas_from_snapshot_uses_embedded_when_cleaned_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedded_df = pd.DataFrame(
        {
            "drama_id": [1],
            "title": ["Embedded"],
            "synopsis": [""],
            "genres": ["Drama"],
            "note_moyenne": [8.2],
        }
    )
    raw_empty_titles = pd.DataFrame(
        {
            "titre": [None, "   "],
            "synopsis": [None, None],
            "genres": [None, None],
            "note_moyenne": [None, None],
        }
    )

    monkeypatch.setattr(
        data_loader.pd, "read_csv", lambda *_args, **_kwargs: raw_empty_titles
    )
    monkeypatch.setattr(data_loader, "_load_embedded_catalog", lambda: embedded_df)

    got = data_loader._load_dramas_from_snapshot(Path(__file__))
    assert got is embedded_df


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
    assert (interactions_df["user_id"] < 0).all()
    assert interactions_df["rating"].between(1.0, 10.0).all()
    assert interactions_df.duplicated(subset=["user_id", "drama_id"]).sum() == 0


def test_load_real_interactions_aggregates_notes_history_favorites_and_interest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = _FakeEngine(
        _FakeConnection(
            query_results={
                "from kdrama.notes": _FakeResult(
                    [(1, 10, 8.0)],
                    ["user_id", "drama_id", "note"],
                ),
                "from kdrama.historique_visionnage": _FakeResult(
                    [(2, 20, 3, "abandonne"), (3, 30, 16, "termine")],
                    ["user_id", "drama_id", "episodes_vus", "statut"],
                ),
                "from kdrama.favoris": _FakeResult(
                    [(1, 10)],
                    ["user_id", "drama_id"],
                ),
                "from kdrama.interet_utilisateur": _FakeResult(
                    [(1, 10, True), (2, 20, False)],
                    ["user_id", "drama_id", "interesse"],
                ),
            }
        )
    )
    monkeypatch.setattr(
        data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine
    )

    got = data_loader.load_real_interactions_from_etape1(db_url="postgresql://fake")

    assert list(got.columns) == ["user_id", "drama_id", "rating"]
    assert len(got) == 3
    assert got.loc[(got["user_id"] == 1) & (got["drama_id"] == 10), "rating"].iloc[0] == pytest.approx(9.14, rel=1e-2)
    assert got.loc[(got["user_id"] == 2) & (got["drama_id"] == 20), "rating"].iloc[0] < 2.0
    assert got.loc[(got["user_id"] == 3) & (got["drama_id"] == 30), "rating"].iloc[0] == pytest.approx(8.8, rel=1e-2)
    assert fake_engine.disposed is True


def test_fetch_user_preferences_returns_expected_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = _FakeEngine(
        _FakeConnection(
            query_results={
                "from kdrama.utilisateurs": _FakeResult(
                    [(True,)],
                    ["fin_heureuse_uniquement"],
                ),
                "from kdrama.utilisateur_genres_preferes": _FakeResult(
                    [("Romance",), ("Thriller",)],
                    ["genre_name"],
                ),
                "from kdrama.utilisateur_acteurs_preferes": _FakeResult(
                    [("Lee Min-ho",), ("Kim Soo-hyun",)],
                    ["actor_name"],
                ),
                "from kdrama.favoris": _FakeResult(
                    [(10,), (11,)],
                    ["drama_id"],
                ),
                "from kdrama.interet_utilisateur": _FakeResult(
                    [(12, True), (13, False)],
                    ["drama_id", "interesse"],
                ),
            }
        )
    )
    monkeypatch.setattr(
        data_loader, "create_engine", lambda *_args, **_kwargs: fake_engine
    )

    prefs = data_loader.fetch_user_preferences(7, db_url="postgresql://fake")

    assert prefs["user_id"] == 7
    assert prefs["happy_ending_only"] is True
    assert prefs["favorite_genres"] == ["Romance", "Thriller"]
    assert prefs["favorite_actors"] == ["Lee Min-ho", "Kim Soo-hyun"]
    assert prefs["favorite_drama_ids"] == [10, 11]
    assert prefs["interested_drama_ids"] == [12]
    assert prefs["disliked_drama_ids"] == [13]


def test_load_real_data_uses_real_interactions_when_enough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dramas_df = pd.DataFrame({"drama_id": [1], "note_moyenne": [8.0], "title": ["A"], "synopsis": [""], "genres": ["Drama"]})
    real_interactions = pd.DataFrame(
        {
            "user_id": list(range(1, data_loader.MIN_REAL_INTERACTIONS + 1)),
            "drama_id": [1] * data_loader.MIN_REAL_INTERACTIONS,
            "rating": [8.0] * data_loader.MIN_REAL_INTERACTIONS,
        }
    )

    monkeypatch.setattr(data_loader, "load_dramas_from_etape1", lambda *_args, **_kwargs: dramas_df)
    monkeypatch.setattr(
        data_loader,
        "load_real_interactions_from_etape1",
        lambda *_args, **_kwargs: real_interactions,
    )

    got_dramas, got_interactions = data_loader.load_real_data(db_url="postgresql://fake")
    assert got_dramas is dramas_df
    assert got_interactions is real_interactions


def test_load_real_data_falls_back_to_synthetic_when_real_insufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dramas_df = pd.DataFrame(
        {
            "drama_id": [1, 2],
            "title": ["A", "B"],
            "synopsis": ["", ""],
            "genres": ["Drama", "Comedy"],
            "note_moyenne": [8.0, 7.0],
        }
    )
    real_interactions = pd.DataFrame({"user_id": [1], "drama_id": [1], "rating": [9.0]})
    synthetic_interactions = pd.DataFrame(
        {"user_id": [-1, -2], "drama_id": [1, 2], "rating": [8.0, 7.5]}
    )

    monkeypatch.setattr(data_loader, "load_dramas_from_etape1", lambda *_args, **_kwargs: dramas_df)
    monkeypatch.setattr(
        data_loader,
        "load_real_interactions_from_etape1",
        lambda *_args, **_kwargs: real_interactions,
    )
    monkeypatch.setattr(
        data_loader,
        "generate_interactions_from_catalog",
        lambda *_args, **_kwargs: synthetic_interactions,
    )

    _, got_interactions = data_loader.load_real_data(db_url="postgresql://fake")
    assert len(got_interactions) == 3
    assert set(got_interactions["user_id"]) == {1, -1, -2}


def test_load_real_data_orchestration_falls_back_on_interaction_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dramas_df = pd.DataFrame(
        {
            "drama_id": [1, 2],
            "title": ["A", "B"],
            "synopsis": ["", ""],
            "genres": ["Drama", "Comedy"],
            "note_moyenne": [8.0, 7.0],
        }
    )
    synthetic_interactions = pd.DataFrame(
        {"user_id": [1], "drama_id": [1], "rating": [8.2]}
    )
    called: dict[str, object] = {}

    monkeypatch.setattr(data_loader, "load_dramas_from_etape1", lambda db_url=None: dramas_df)

    def _raise(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("db down")

    def _fake_generate(
        input_df: pd.DataFrame,
        num_users: int = 50,
        avg_interactions_per_user: int = 8,
        noise_std: float = 1.0,
        random_state: int = 42,
    ) -> pd.DataFrame:
        called["same_df"] = input_df is dramas_df
        called["num_users"] = num_users
        called["avg"] = avg_interactions_per_user
        called["noise_std"] = noise_std
        called["random_state"] = random_state
        return synthetic_interactions

    monkeypatch.setattr(data_loader, "load_real_interactions_from_etape1", _raise)
    monkeypatch.setattr(data_loader, "generate_interactions_from_catalog", _fake_generate)

    got_dramas, got_interactions = data_loader.load_real_data(
        db_url="postgresql://fake",
        num_users=7,
        avg_interactions_per_user=4,
    )

    assert got_dramas is dramas_df
    assert got_interactions is synthetic_interactions
    assert called["same_df"] is True
    assert called["num_users"] == 7
    assert called["avg"] == 4
