import streamlit as st
import streamlit.components.v1 as components
from services.ar.service import ARService, ARHistory
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="Learn with AR - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

# Detecting if user device supports AR
if "device_supports_ar" not in st.session_state:
    device_type = st.session_state.get("user_device_type", "mobile")
    st.session_state["device_supports_ar"] = False if device_type == "pc" else True

# ---------------------------------------------------------
# STEPS CONFIG
# ---------------------------------------------------------
STEP_INPUT = "input"
STEP_CHOOSE = "choose_model"
STEP_VIEW = "view"

# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def reset_ar():
    for ss_name in [
        "id",
        "ar_model_id",
        "ar_topic",
        "found_models",
        "selected_model",
        "sketchfab_embed_html",
        "ai_description",
        "model_viewer_html",
    ]:
        if ss_name in st.session_state:
            del st.session_state[ss_name]

    st.session_state["generated_ar"] = False
    st.session_state["choose_to_view_from"] = "choose"


def navigate_to(step: str):
    st.session_state["ar_step"] = step
    st.rerun()


def title_and_navigation_row(
    back_nav: str,
    title: str,
    disable_back_btn: bool = False,
):
    if st.session_state.get("user_device_type", "mobile") == "mobile":
        col1, col2 = st.columns(2)

        if col1.button(
            "Back", icon="🔙", use_container_width=True, disabled=disable_back_btn
        ):
            navigate_to(back_nav)

        if col2.button("Reset", icon="🔄", use_container_width=True):
            reset_ar()
            navigate_to(STEP_INPUT)

        st.title(title, text_alignment="center", anchor=False)

    else:
        col1, col2, col3 = st.columns([1, 5, 1], vertical_alignment="bottom")

        if col1.button("Back", icon="🔙", disabled=disable_back_btn):
            navigate_to(back_nav)

        col2.title(title, text_alignment="center", anchor=False)

        if col3.button("Reset", icon="🔄"):
            reset_ar()
            navigate_to(STEP_INPUT)


@st.cache_resource
def get_ar_services(sketchfab_key, gh_username, gh_token, gh_repo):
    client = st.session_state["client"]
    return (
        ARService(sketchfab_key, gh_username, gh_token, gh_repo, client),
        ARHistory(st.session_state["root_ref"]),
    )


# Initializing AR Services
github_secrets = st.secrets["github"]
ar_service, ar_history = get_ar_services(
    sketchfab_key=st.secrets["SKETCHFAB_API_KEY"],
    gh_username=github_secrets["USERNAME"],
    gh_token=github_secrets["ACCESS_TOKEN"],
    gh_repo=github_secrets["REPO"],
)

# ---------------------------------------------------------
# STEP 0: INPUT AND HISTORY
# ---------------------------------------------------------


def input_and_history():
    st.title(
        "🥽 Learn with AR",
        anchor=False,
        help="AR is a technology that puts interactive digital 3D models into your real world using your device's camera.",
    )
    "---"

    with st.form("learn_with_ar", border=False):
        topic = st.text_input("Topic")

        if (
            st.form_submit_button(
                "Search 3D Models",
                type="primary",
                icon="🔍",
                use_container_width=True,
            )
            and topic.strip()
        ):
            topic = topic.title()

            with st.spinner("Searching for 3D models...", show_time=True):
                models = ar_service.search_models(topic)

            if models:
                st.session_state["ar_topic"] = topic
                st.session_state["found_models"] = models
                st.session_state["selected_model"] = None
                navigate_to(STEP_CHOOSE)
            else:
                st.error("No models found for this topic. Try a different search.")

    "---"

    with st.expander("📂 History"):
        ar_data = []
        if st.session_state.get("user"):
            ar_data = ar_history.get_saved_ar_data(st.session_state["user"]["uid"])

        if ar_data:
            streamlit_colors = ["red", "blue", "orange", "yellow", "green", "violet", "gray"]

            for i, model in enumerate(ar_data):
                # Pick the color dynamically based on the current loop index
                chosen_color = streamlit_colors[i % len(streamlit_colors)]

                col1, col2 = st.columns(2, vertical_alignment="top")
                with col1:
                    st.subheader(f":{chosen_color}[{model['topic']}]", anchor=False)

                    timestamp = model.get("created_at", "Unknown")
                    try:
                        dt = datetime.fromtimestamp(timestamp)
                        date_time = dt.strftime("%B %d, %Y at %I:%M %p")
                        st.caption(f"Created: {date_time}")
                    except:
                        ...
                with col2:
                    if model.get("thumbnail_url"):
                        st.image(model["thumbnail_url"], width=200)

                # description = model.get("ai_description", "")
                # if description:
                #     minimized_description = (
                #         description[:150] + "..."
                #         if len(description) > 200
                #         else description
                #     )
                #     st.write(f"**{minimized_description}**")

                col1, col2, _ = st.columns([0.95, 1, 4])

                with col1:
                    if st.button("View", key=f"view_model_{model['id']}", icon="👀"):
                        sketchfab_uid = model.get("sketchfab_uid", "")
                        if not sketchfab_uid and "embed" in model.get("sketchfab_embed_html", ""):
                            try:
                                sketchfab_uid = model["sketchfab_embed_html"].split("/models/")[1].split("/embed")[0]
                            except IndexError:
                                sketchfab_uid = ""

                        # Reconstruct selected_model structure so AR/AI buttons work seamlessly
                        st.session_state["selected_model"] = {
                            "uid": sketchfab_uid,
                            "name": model["topic"],
                            "description": model.get("ai_description", ""),
                            "thumbnails": {
                                "images": [
                                    {"url": model.get("thumbnail_url", "")},
                                    {"url": model.get("thumbnail_url", "")},
                                ]
                            },
                        }
                        st.session_state["generated_ar"] = True
                        st.session_state["ar_topic"] = model["topic"]
                        st.session_state["ar_model_id"] = model["id"]
                        st.session_state["sketchfab_embed_html"] = model[
                            "sketchfab_embed_html"
                        ]
                        st.session_state["ai_description"] = model.get(
                            "ai_description", ""
                        )
                        st.session_state["model_viewer_html"] = model.get(
                            "model_viewer_html"
                        )
                        st.session_state["choose_to_view_from"] = "history"
                        navigate_to(STEP_VIEW)

                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{model['id']}"):
                        ar_history.delete_ar_experience(
                            st.session_state["user"]["uid"], model["id"]
                        )
                        st.success(f"Deleted '{model['topic']}'")
                        st.rerun()

                if i != len(ar_data) - 1:
                    "---"
        else:
            st.info("No AR models found. Create your first one!")


# ---------------------------------------------------------
# STEP 1: CHOOSE MODEL
# ---------------------------------------------------------


def choose_model():
    title_and_navigation_row(STEP_INPUT, "Choose a 3D Model")
    " "
    st.write(f"Select a 3D model for: :blue[**{st.session_state['ar_topic']}**]")

    models = st.session_state["found_models"]

    # Render in explicit 2-column rows for clean layout across screen sizes
    for i in range(0, len(models), 2):
        row_models = models[i : i + 2]
        cols = st.columns(2)

        for idx, model in enumerate(row_models):
            with cols[idx]:
                images = model.get("thumbnails", {}).get("images", [])
                thumb_url = (
                    images[1]["url"]
                    if len(images) > 1
                    else (images[0]["url"] if images else "")
                )

                if thumb_url:
                    st.image(thumb_url, use_container_width=True)

                st.markdown(f"**{model.get('name', '3D Model')}**")

                if st.button(
                    "Select Model",
                    key=f"select_model_{model['uid']}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state["selected_model"] = model
                    st.session_state["sketchfab_embed_html"] = (
                        ar_service.sketchfab_embed_html(model["uid"])
                    )
                    st.session_state["generated_ar"] = True
                    st.session_state["choose_to_view_from"] = "choose"
                    navigate_to(STEP_VIEW)


# ---------------------------------------------------------
# STEP 2: DISPLAY MODEL - AI DESCRIPTION - SHOW IN AR
# ---------------------------------------------------------


def view_model():
    disable_btn = False
    if st.session_state.get("choose_to_view_from", "choose") == "history":
        disable_btn = True

    title_and_navigation_row(STEP_CHOOSE, "AR Experience", disable_back_btn=disable_btn)
    st.subheader(
        f":blue[{st.session_state['ar_topic']}]", anchor=False, text_alignment="center"
    )

    st.iframe(st.session_state["sketchfab_embed_html"])
    "---"

    if st.session_state.get("ai_description"):
        st.markdown(st.session_state["ai_description"])
        "---"

    if st.session_state.get("model_viewer_html") and st.session_state.get(
        "device_supports_ar"
    ):
        components.html(st.session_state["model_viewer_html"], height=50)
        "---"

    col_ai, col_ar = st.columns(2)

    with col_ai:
        if st.button(
            "✨ Generate AI Description",
            type="primary",
            use_container_width=True,
            disabled=bool(st.session_state.get("ai_description")),
        ):
            with st.spinner("Generating AI explanation...", show_time=True):
                description = ar_service.generate_ai_description(
                    st.session_state["ar_topic"], st.session_state["selected_model"]
                )
                st.session_state["ai_description"] = description

                # Dynamically update existing history node if viewing a saved model
                if st.session_state.get("user") and st.session_state.get("ar_model_id"):
                    ar_history.update_ar_experience(
                        st.session_state["user"]["uid"],
                        st.session_state["ar_model_id"],
                        {"ai_description": description},
                    )

                st.rerun()

    with col_ar:
        if not st.session_state.get("model_viewer_html"):
            ar_disabled = not st.session_state.get("device_supports_ar")
            help_text = "This device does not support AR" if ar_disabled else None

            if st.button(
                "📱 Prepare for AR",
                use_container_width=True,
                disabled=ar_disabled,
                help=help_text,
            ):
                model_uid = st.session_state["selected_model"]["uid"]
                with st.spinner("Preparing model for AR...", show_time=True):
                    model_bytes = ar_service.download_model(model_uid)
                    hosted_url = ar_service.host_model_on_github(
                        st.session_state["ar_topic"], model_bytes
                    )
                    model_viewer_html = ar_service.model_viewer_html(hosted_url)
                    st.session_state["model_viewer_html"] = model_viewer_html

                    # Dynamically update existing history node if viewing a saved model
                    if st.session_state.get("user") and st.session_state.get("ar_model_id"):
                        ar_history.update_ar_experience(
                            st.session_state["user"]["uid"],
                            st.session_state["ar_model_id"],
                            {"model_viewer_html": model_viewer_html},
                        )

                    st.rerun()

    # Save initial entry logic for authenticated users
    if (
        not st.session_state.get("ar_model_id")
        and st.session_state.get("ar_topic")
        and st.session_state.get("sketchfab_embed_html")
    ):
        if not st.session_state.get("user") and not st.session_state.get(
            "ar_sign_in_offer"
        ):
            st.session_state["ar_sign_in_offer"] = True

            @st.dialog("Get Started")
            def sign_in_offer():
                st.info("Sign In to start saving your history!")
                col1, col2 = st.columns(2)

                if col1.button("Sign In", icon="🔐", use_container_width=True):
                    st.session_state["page_before_auth"] = "ar"
                    st.switch_page("pages/signin.py")

                if col2.button(
                    "Create Account",
                    type="primary",
                    icon="👤",
                    use_container_width=True,
                ):
                    st.session_state["page_before_auth"] = "ar"
                    st.switch_page("pages/signup.py")

            sign_in_offer()

        elif st.session_state.get("user"):
            selected_model = st.session_state.get("selected_model", {})
            images = selected_model.get("thumbnails", {}).get("images", [])
            thumb_url = (
                images[1]["url"]
                if len(images) > 1
                else (images[0]["url"] if images else "")
            )

            with st.spinner("Saving the AR model...", show_time=True):
                id = ar_history.save_ar_experience(
                    user_uid=st.session_state["user"]["uid"],
                    topic=st.session_state["ar_topic"],
                    sketchfab_embed_html=st.session_state["sketchfab_embed_html"],
                    sketchfab_uid=selected_model.get("uid", ""),
                    thumbnail_url=thumb_url,
                    ai_description=st.session_state.get("ai_description", ""),
                    model_viewer_html=st.session_state.get("model_viewer_html", None),
                )
                st.session_state["ar_model_id"] = id

    if st.button(
        "Generate a new AR experience",
        type="secondary",
        icon="✨",
        use_container_width=True,
    ):
        reset_ar()
        navigate_to(STEP_INPUT)


# ---------------------------------------------------------
# PAGE ROUTER
# ---------------------------------------------------------

step = st.session_state.get("ar_step", STEP_INPUT)

if step == STEP_INPUT:
    input_and_history()

elif step == STEP_CHOOSE:
    choose_model()

elif step == STEP_VIEW:
    view_model()
