import streamlit as st
import streamlit.components.v1 as components
from learning_plans.service import LearningPlansService
from firebase_admin.db import Reference

# Initializing DB Refrences
root_ref: Reference = st.session_state["root_ref"]
users_ref = root_ref.child("users")


def display_lp(username: str, lp: dict):
    id = lp["id"]
    if username and (
        current_day := users_ref.child(f"{username}/history/lp/{id}/current_day").get()
    ):
        current_day

    else:
        current_day = 1

    st.header(f"Day {current_day}")
    day_data = lp["days"][current_day - 1]

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📄 Content", "🎥 Video", "🗃️ Flashcards", "📃 Quiz"]
    )

    tab1.markdown(day_data["text"])

    youtube_embed_html = LearningPlansService.youtube_embed_html(day_data["video"])
    with tab2:
        components.html(youtube_embed_html)
    
    flashcards: list = day_data["flashcards"]
    with tab3:
        for card in flashcards:
            ...


if not st.session_state.get("generate_btn_clicked"):
    st.title("📚 Learning Plans", anchor=False)
    "---"

    st.header("📙 Learning Plan", anchor=False)

    # Plan Title
    title = st.text_input("🏷️ **Plan Title**")
    " "

    # Description
    description = st.text_area(
        "📄 **Description** (optional)",
        height=150,
        placeholder="Describe the topics you want covered, custom instructions to the AI model, etc",
    )

    # Age & Flashcards Number
    col1, col2 = st.columns(2)
    age = col1.number_input("**Age**", min_value=1, max_value=150, value=10)
    flashcards_num = st.number_input(
        "**Number of Flashcards**",
        min_value=1,
        max_value=50,
        value=5,
        help="The number of flashcards for all the days.",
        icon="🗂️",
    )

    # Days Number
    days_num = st.slider(
        "🎯 **Number of Days**",
        min_value=1,
        max_value=31,
        value=7,
    )
    ar = st.checkbox("Include an AR Model", value=True)
    use_model_viewer = st.checkbox(
        "View the AR model in your space (more time).",
        disabled=True if not ar else False,
    )

    if st.button(
        "Generate Learning Plan", type="primary", icon="✨", use_container_width=True
    ):
        params = [title, age, days_num, description, flashcards_num]
        if ar:
            SKETCHFAB_API_KEY = st.secrets["SKETCHFAB_API_KEY"]
            github_secrets = st.secrets["github"]
            GITHUB_USERNAME = github_secrets["USERNAME"]
            GITHUB_ACCESS_TOKEN = github_secrets["ACCESS_TOKEN"]
            REPO = github_secrets["REPO"]

            params.extend(
                [
                    ar,
                    use_model_viewer,
                    SKETCHFAB_API_KEY,
                    GITHUB_USERNAME,
                    GITHUB_ACCESS_TOKEN,
                    REPO,
                ]
            )

        st.session_state["params"] = params
        st.session_state["generate_btn_clicked"] = True
        st.rerun()

else:
    st.title(f"📚 Learning Plan - {st.session_state["params"]["title"]}")
    "---"

    if not st.session_state["generated_plan"]:
        lp_service = LearningPlansService(st.session_state["client"])

        for result in lp_service.generate_learning_plan(*st.session_state["params"]):
            if result["step"] == "lp":
                lp = result["lp"]
                st.session_state["lp"] = lp

            if result["step"] == "ar":
                components.html(result["sketchfab_embed_html"])
                st.markdown(result["ai_description"])
