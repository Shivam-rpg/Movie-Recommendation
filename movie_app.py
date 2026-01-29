import os
import requests
import streamlit as st

# =============================
# CONFIG
# =============================
API_BASE = os.getenv("API_BASE", "https://movie-rec-466x.onrender.com")
TMDB_IMG = "https://image.tmdb.org/t/p/w500"

st.set_page_config(
    page_title="Movie Recommender",
    page_icon="🎬",
    layout="wide",
)

# =============================
# STYLES
# =============================
st.markdown(
    """
<style>
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px; }
.small-muted { color:#6b7280; font-size: 0.92rem; }
.movie-title { font-size: 0.9rem; line-height: 1.15rem; height: 2.3rem; overflow: hidden; }
.card { border: 1px solid rgba(0,0,0,0.08); border-radius: 16px; padding: 14px; background: rgba(255,255,255,0.7); }
</style>
""",
    unsafe_allow_html=True,
)

# =============================
# STATE
# =============================
if "view" not in st.session_state:
    st.session_state.view = "home"
if "selected_tmdb_id" not in st.session_state:
    st.session_state.selected_tmdb_id = None

# =============================
# ROUTING HELPERS
# =============================
def goto_home():
    st.session_state.view = "home"
    st.session_state.selected_tmdb_id = None
    st.query_params.clear()
    st.rerun()


def goto_details(tmdb_id: int):
    st.session_state.view = "details"
    st.session_state.selected_tmdb_id = int(tmdb_id)
    st.query_params["view"] = "details"
    st.query_params["id"] = str(tmdb_id)
    st.rerun()


# =============================
# API HELPER (FIXED)
# =============================
@st.cache_data(ttl=600)
def api_get_json(endpoint, params=None):
    try:
        r = requests.get(
            f"{API_BASE}{endpoint}",
            params=params,
            timeout=60,
        )
        r.raise_for_status()
        return r.json(), None
    except Exception as e:
        return None, str(e)


# =============================
# UI HELPERS
# =============================
def poster_grid(cards, cols=6, key_prefix="grid"):
    if not cards:
        st.info("No movies to show.")
        return

    rows = (len(cards) + cols - 1) // cols
    i = 0
    for _ in range(rows):
        colset = st.columns(cols)
        for c in range(cols):
            if i >= len(cards):
                break
            m = cards[i]
            i += 1

            with colset[c]:
                if m.get("poster_url"):
                    st.image(m["poster_url"], use_column_width=True)
                else:
                    st.write("🖼️ No poster")

                if st.button("Open", key=f"{key_prefix}_{m['tmdb_id']}_{i}"):
                    goto_details(m["tmdb_id"])

                st.markdown(
                    f"<div class='movie-title'>{m.get('title','')}</div>",
                    unsafe_allow_html=True,
                )


def to_cards_from_tfidf_items(items):
    cards = []
    for x in items or []:
        tmdb = x.get("tmdb")
        if tmdb and tmdb.get("tmdb_id"):
            cards.append(
                {
                    "tmdb_id": tmdb["tmdb_id"],
                    "title": tmdb.get("title"),
                    "poster_url": tmdb.get("poster_url"),
                }
            )
    return cards


# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.markdown("## 🎬 Menu")

    if st.button("🏠 Home"):
        goto_home()

    st.markdown("---")
    home_category = st.selectbox(
        "Home Category",
        ["trending", "popular", "top_rated", "now_playing", "upcoming"],
    )

    grid_cols = st.slider("Grid columns", 4, 8, 6)


# =============================
# HEADER
# =============================
st.title("🎬 Movie Recommender")
st.caption("Search → open → recommendations (TF-IDF + Genre)")
st.divider()

# =====================================================
# HOME VIEW
# =====================================================
if st.session_state.view == "home":

    query = st.text_input(
        "Search movie",
        placeholder="Type: avengers, batman, love...",
    )

    # ---------- SEARCH ----------
    if query.strip():
        data, err = api_get_json("/tmdb/search", {"query": query})
        if err:
            st.error(err)
        else:
            results = data.get("results", [])
            cards = []
            for m in results[:24]:
                cards.append(
                    {
                        "tmdb_id": m["id"],
                        "title": m.get("title"),
                        "poster_url": (
                            f"{TMDB_IMG}{m['poster_path']}"
                            if m.get("poster_path")
                            else None
                        ),
                    }
                )

            st.markdown("### Results")
            poster_grid(cards, cols=grid_cols, key_prefix="search")

        st.stop()

    # ---------- HOME FEED ----------
    st.markdown(f"### 🏠 {home_category.replace('_',' ').title()}")

    home_cards, err = api_get_json(
        "/home", {"category": home_category, "limit": 24}
    )

    if err or not home_cards:
        st.error(f"Home feed failed: {err}")
        st.stop()

    poster_grid(home_cards, cols=grid_cols, key_prefix="home")


# =====================================================
# DETAILS VIEW
# =====================================================
elif st.session_state.view == "details":

    tmdb_id = st.session_state.selected_tmdb_id
    if not tmdb_id:
        goto_home()

    data, err = api_get_json(f"/movie/id/{tmdb_id}")
    if err:
        st.error(err)
        st.stop()

    col1, col2 = st.columns([1, 2.5])

    with col1:
        if data.get("poster_url"):
            st.image(data["poster_url"], use_column_width=True)

    with col2:
        st.markdown(f"## {data.get('title')}")
        st.caption(f"Release: {data.get('release_date','-')}")
        st.write(data.get("overview") or "No overview available.")

    if data.get("backdrop_url"):
        st.image(data["backdrop_url"], use_column_width=True)

    st.divider()
    st.markdown("### ✅ Recommendations")

    title = data.get("title")
    bundle, err = api_get_json(
        "/movie/search",
        {"query": title, "tfidf_top_n": 12, "genre_limit": 12},
    )

    if not err and bundle:
        st.markdown("#### 🔎 Similar Movies (TF-IDF)")
        poster_grid(
            to_cards_from_tfidf_items(bundle.get("tfidf_recommendations")),
            cols=grid_cols,
            key_prefix="tfidf",
        )

        st.markdown("#### 🎭 Genre Based")
        poster_grid(
            bundle.get("genre_recommendations"),
            cols=grid_cols,
            key_prefix="genre",
        )
    else:
        st.warning("No recommendations available.")

