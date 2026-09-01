from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_loader import _load_embedded_catalog, generate_interactions_from_catalog  # noqa: E402
from recommendation_model import DEFAULT_MODEL_DIR, HybridRecommender, load_real_data  # noqa: E402

MODEL_API_URL = os.getenv("MODEL_API_URL")
MODEL_API_TOKEN = os.getenv("MODEL_API_TOKEN")


def _parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _available_choices(model: HybridRecommender) -> tuple[list[str], list[str]]:
    dramas_df = model.dramas_df
    if dramas_df is None:
        return [], []

    genre_choices: set[str] = set()
    actor_choices: set[str] = set()
    for _, row in dramas_df.iterrows():
        genre_choices.update(row.get("genre_list", []) or [])
        actor_choices.update(row.get("actor_list", []) or [])
    return sorted(genre_choices), sorted(actor_choices)


@st.cache_resource(show_spinner="Loading recommendation model...")
def load_model() -> HybridRecommender:
    candidate_dirs = [ROOT_DIR / "model_artifacts", DEFAULT_MODEL_DIR]
    for model_dir in candidate_dirs:
        try:
            return HybridRecommender.load(model_dir)
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


def _call_local_model(model: HybridRecommender, payload: dict[str, object]) -> list[dict[str, object]]:
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
        user_id = None if guest_mode else st.number_input("User ID", min_value=1, value=1, step=1)
        selected_genres = st.multiselect("Favorite genres", genre_choices)
        selected_actors = st.multiselect("Favorite actors", actor_choices[:150])
        actor_text = st.text_input("Extra actors (comma-separated)")
        mood = st.selectbox(
            "Mood",
            ["", "feel good", "romantic", "suspenseful", "emotional", "comforting"],
        )
        text_request = st.text_area(
            "Free-text request",
            placeholder="e.g. a cozy romance with strong chemistry and a happy ending",
        )
        happy_ending_only = st.checkbox("Happy ending only", value=False)
        top_k = st.slider("Number of recommendations", min_value=1, max_value=10, value=4)
        use_live_api = st.checkbox(
            "Use live FastAPI endpoint",
            value=False,
            disabled=not bool(MODEL_API_URL),
            help="Requires MODEL_API_URL and MODEL_API_TOKEN.",
        )

    all_actors = selected_actors + _parse_list(actor_text)
    unique_actors: list[str] = []
    for actor in all_actors:
        if actor not in unique_actors:
            unique_actors.append(actor)

    payload: dict[str, object] = {
        "user_id": None if guest_mode else int(user_id),
        "top_k": top_k,
        "mood": mood or None,
        "text": text_request.strip() or None,
        "genres": selected_genres or None,
        "actor_names": unique_actors or None,
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
                _call_live_api(payload) if use_live_api else _call_local_model(model, payload)
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
                            st.image(str(poster), use_container_width=True)
                    with right:
                        st.subheader(str(rec.get("title") or rec.get("titre") or "Unknown"))
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
