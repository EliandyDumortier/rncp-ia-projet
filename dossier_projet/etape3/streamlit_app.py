from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_loader import (  # noqa: E402
    _load_embedded_catalog,
    generate_interactions_from_catalog,
)
from recommendation_model import (  # noqa: E402
    DEFAULT_MODEL_DIR,
    HybridRecommender,
    load_real_data,
)

MODEL_API_URL = os.getenv("MODEL_API_URL")
MODEL_API_TOKEN = os.getenv("MODEL_API_TOKEN")


def _actor_entries(value: Any) -> list[Any]:
    """Return actor catalog entries without exposing their metadata in the UI."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _actor_names_from_row(row: Any) -> set[str]:
    names: set[str] = set()
    for actor in _actor_entries(row.get("acteurs")):
        if isinstance(actor, dict):
            name = str(actor.get("nom") or "").strip()
        elif isinstance(actor, str):
            name = actor.strip()
        else:
            name = ""
        if name:
            names.add(name)

    if names:
        return names

    # Embedded/demo catalogs already contain a clean actor_list. Ignore
    # serialized dictionaries from older artifacts instead of showing them.
    for actor in row.get("actor_list", []) or []:
        if isinstance(actor, str):
            name = actor.strip()
            if name and "{" not in name and "}" not in name:
                names.add(name)
    return names


def _available_choices(model: HybridRecommender) -> tuple[list[str], list[str]]:
    dramas_df = model.dramas_df
    if dramas_df is None:
        return [], []

    genre_choices: set[str] = set()
    actor_choices: set[str] = set()
    for _, row in dramas_df.iterrows():
        genre_choices.update(row.get("genre_list", []) or [])
        actor_choices.update(_actor_names_from_row(row))
    return sorted(genre_choices), sorted(actor_choices, key=str.casefold)


def _restore_query_encoder(model: HybridRecommender) -> HybridRecommender:
    """Restore the encoder intentionally omitted from serialized artifacts."""
    model._load_embedding_model()
    if model._embedding_model.__class__.__name__ == "_TFIDFFallback":
        # A fresh TF-IDF encoder must be fitted on the catalog so queries and
        # persisted content embeddings use the same vector space.
        model._generate_content_embeddings()
    return model


@st.cache_resource(show_spinner="Loading recommendation model...")
def load_model() -> HybridRecommender:
    candidate_dirs = [ROOT_DIR / "model_artifacts", DEFAULT_MODEL_DIR]
    for model_dir in candidate_dirs:
        try:
            return _restore_query_encoder(HybridRecommender.load(model_dir))
        except Exception:
            continue

    try:
        dramas_df, interactions_df = load_real_data()
    except Exception:
        dramas_df = _load_embedded_catalog()
        interactions_df = generate_interactions_from_catalog(dramas_df)
    model = HybridRecommender(alpha=0.6)
    model.train(dramas_df, interactions_df)
    return model


def _call_live_api(payload: dict[str, object]) -> list[dict[str, object]]:
    if not MODEL_API_URL:
        raise RuntimeError("MODEL_API_URL is not configured.")
    if not MODEL_API_TOKEN:
        raise RuntimeError("MODEL_API_TOKEN is required for the live API mode.")

    response = httpx.post(
        f"{MODEL_API_URL.rstrip('/')}/recommend",
        json=payload,
        headers={"Authorization": f"Bearer {MODEL_API_TOKEN}"},
        timeout=20.0,
    )
    response.raise_for_status()
    return response.json().get("recommendations", [])


def _call_local_model(
    model: HybridRecommender, payload: dict[str, object]
) -> list[dict[str, object]]:
    user_preferences = {
        "favorite_genres": payload.get("genres") or [],
        "favorite_actors": payload.get("actor_names") or [],
        "happy_ending_only": bool(payload.get("happy_ending_only", False)),
        "favorite_drama_ids": [],
        "interested_drama_ids": [],
        "disliked_drama_ids": [],
    }
    results = model.recommend(
        user_id=payload.get("user_id"),  # type: ignore[arg-type]
        drama_id=payload.get("drama_id"),  # type: ignore[arg-type]
        top_k=int(payload.get("top_k", 4)),
        mood=payload.get("mood"),  # type: ignore[arg-type]
        text=payload.get("text"),  # type: ignore[arg-type]
        genres=payload.get("genres"),  # type: ignore[arg-type]
        actor_names=payload.get("actor_names"),  # type: ignore[arg-type]
        happy_ending_only=payload.get("happy_ending_only"),  # type: ignore[arg-type]
        user_preferences=user_preferences,
    )
    return [result.to_dict() for result in results]


def main() -> None:
    st.set_page_config(page_title="K-Drama Recommender POC", layout="wide")
    st.title("K-Drama Recommender — Streamlit POC")
    st.caption("Guest or user-centric recommendation demo powered by the step 3 model.")

    model = load_model()
    genre_choices, actor_choices = _available_choices(model)

    with st.sidebar:
        st.header("Preferences")
        guest_mode = st.toggle("Guest mode", value=True)
        user_id = (
            None
            if guest_mode
            else st.number_input("User ID", min_value=1, value=1, step=1)
        )
        selected_genres = st.multiselect("Favorite genres", genre_choices)
        selected_actors = st.multiselect(
            "Favorite actors",
            actor_choices,
            max_selections=5,
            help="Actor names come from the same K-Drama catalog as the web application.",
        )
        mood = st.selectbox(
            "Mood",
            ["", "feel good", "romantic", "suspenseful", "emotional", "comforting"],
        )
        text_request = st.text_area(
            "Free-text request",
            placeholder="e.g. a cozy romance with strong chemistry and a happy ending",
        )
        happy_ending_only = st.checkbox("Happy ending only", value=False)
        top_k = st.slider(
            "Number of recommendations", min_value=1, max_value=10, value=4
        )
        use_live_api = st.checkbox(
            "Use live FastAPI endpoint",
            value=False,
            disabled=not bool(MODEL_API_URL),
            help="Requires MODEL_API_URL and MODEL_API_TOKEN.",
        )

    payload: dict[str, object] = {
        "user_id": None if guest_mode else int(user_id),
        "top_k": top_k,
        "mood": mood or None,
        "text": text_request.strip() or None,
        "genres": selected_genres or None,
        "actor_names": selected_actors or None,
        "happy_ending_only": happy_ending_only,
    }

    if st.button("Get recommendations", type="primary"):
        try:
            if not any(
                [
                    payload["user_id"] is not None,
                    payload["text"],
                    payload["genres"],
                    payload["actor_names"],
                    payload["happy_ending_only"],
                    payload["mood"],
                ]
            ):
                st.warning("Add at least one preference or switch off guest mode.")
                return

            recommendations = (
                _call_live_api(payload)
                if use_live_api
                else _call_local_model(model, payload)
            )
            if not recommendations:
                st.info("No recommendations found for the current filters.")
                return

            for rec in recommendations:
                with st.container(border=True):
                    left, right = st.columns([1, 3])
                    with left:
                        poster = rec.get("poster") or rec.get("poster_url")
                        if poster:
                            st.image(str(poster))
                    with right:
                        st.subheader(
                            str(rec.get("title") or rec.get("titre") or "Unknown")
                        )
                        st.write(f"**Genres:** {', '.join(rec.get('genres', []))}")
                        st.write(f"**Score:** {float(rec.get('score', 0.0)):.2f}")
                        st.write(rec.get("explanation") or rec.get("reason") or "")
                        synopsis = str(rec.get("synopsis") or "").strip()
                        if synopsis:
                            st.caption(synopsis)
        except Exception as exc:
            st.error(f"Unable to generate recommendations: {exc}")


if __name__ == "__main__":
    main()
