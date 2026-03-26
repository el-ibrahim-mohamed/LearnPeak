import streamlit as st
import streamlit.components.v1 as components
from google import genai
from ar.service import ARService
from firebase_admin.db import Reference
import time
from datetime import datetime


# Initializing DB Refrences
root_ref: Reference = st.session_state["root_ref"]
users_ref = root_ref.child("users")

# Detecting the user's device type to customize the layout
if "device_supports_ar" not in st.session_state:
    device_type = st.session_state.get("user_device_type", "pc")
    st.session_state["device_supports_ar"] = False if device_type == "pc" else True

# Scrolling Logic
if st.session_state.get("scroll_to_top"):
    js = """
    <script>
        window.parent.document.querySelector('section.stMain').scrollTo({top: 0});
    </script>
    """
    # behavior: 'smooth'
    st.components.v1.html(js, height=0)
    st.session_state["scroll_to_top"] = False

if st.session_state.get("scroll_to_bottom"):
    js = """
    <script>
        const el = window.parent.document.querySelector('section.stMain');
        el.scrollTo({ top: el.scrollHeight });
    </script>
    """
    # add "behavior: 'smooth'" if you want animation
    st.components.v1.html(js, height=0)
    st.session_state["scroll_to_bottom"] = False


def generate_ar_experience(topic_name: str, use_model_viewer: bool = False):
    # Getting ARService API Keys
    SKETCHFAB_API_KEY = st.secrets["SKETCHFAB_API_KEY"]
    github_secrets = st.secrets["github"]
    GITHUB_USERNAME = github_secrets["USERNAME"]
    GITHUB_ACCESS_TOKEN = github_secrets["ACCESS_TOKEN"]
    REPO = github_secrets["REPO"]
    client: genai.Client = st.session_state["client"]

    arservice = ARService(
        SKETCHFAB_API_KEY, GITHUB_USERNAME, GITHUB_ACCESS_TOKEN, REPO, client
    )

    # Loop through yielded results
    for result in arservice.generate_ar_experience(topic_name, use_model_viewer):

        if result["step"] == "embed_and_description":
            st.session_state["sketchfab_embed_html"] = result["sketchfab_embed_html"]
            st.session_state["ai_description"] = result["ai_description"]

            height = 200 if st.session_state["device_supports_ar"] else 700
            components.html(result["sketchfab_embed_html"], height=height)
            "---"

            st.markdown(result["ai_description"])
            "---"

        elif result["step"] == "ar_viewer":
            st.session_state["model_viewer_html"] = result["model_viewer_html"]
            components.html(result["model_viewer_html"], height=50)
            "---"

    # NOTE: The 3D model embed in the page is shown by sketchfab_embed_html, while it's closed in model_viewer_html
    # A "View in AR" button appears by model_viewer_html when device supports AR


def save_ar_experience(
    username: str,
    topic: str,
    sketchfab_embed_html: str,
    ai_description: str,
    model_viewer_html: str = None,
):
    ar_ref = users_ref.child(f"{username}/history/ar")
    ar_saving_data = {
        "topic": topic,
        "created_at": time.time(),  # Timestamp
        "sketchfab_embed_html": sketchfab_embed_html,
        "ai_description": ai_description,
    }
    if model_viewer_html:
        ar_saving_data["model_viewer_html"] = model_viewer_html

    ar_ref.push(ar_saving_data)  # push automatically creates a long, random key


def get_saved_ar_data(username: str) -> list[dict]:
    ar_ref = users_ref.child(f"{username}/history/ar")
    ar_data_dict: dict = ar_ref.get()

    ar_models = []
    if ar_data_dict:
        for ar_id, ar_model in ar_data_dict.items():
            ar_models.append({"id": ar_id, **ar_model})

        # Sort by most recent
        ar_models.sort(key=lambda x: x.get("created_at", 0), reverse=True)

    return ar_models


def delete_ar_experience(username: str, model_id: str):
    ar_model_to_delete = users_ref.child(f"{username}/history/ar/{model_id}")
    ar_model_to_delete.delete()


if not st.session_state.get("generated_ar"):
    st.title("🔖 Learn with AR", anchor=False)
    "---"

    with st.form("learn_with_ar", border=False):
        # Taking Input
        topic = st.text_input("Topic:")

        if st.session_state["device_supports_ar"]:
            show_in_ar = st.checkbox("Show in AR", value=True)
        else:
            show_in_ar = st.checkbox(
                "Show in AR",
                value=False,
                disabled=True,
                help="This device does not support AR",
            )

        # Generate button
        if (
            st.form_submit_button(
                "Generate AR Experience",
                type="primary",
                icon="✨",
                use_container_width=True,
            )
            and topic
        ):
            st.session_state["topic"] = topic
            st.session_state["show_in_ar"] = show_in_ar
            st.session_state["generated_ar"] = True
            st.rerun()

    "---"
    with st.expander("📂 History"):
        ar_data = []
        if st.session_state.get("user"):
            ar_data = get_saved_ar_data(st.session_state["user"]["username"])

        if ar_data:
            for i, model in enumerate(ar_data):
                col1, col2 = st.columns(
                    [4, 1], gap="large", vertical_alignment="center"
                )

                with col1:
                    st.subheader(f"#{i+1} {model["topic"]}")

                    timestamp = model.get("created_at", "Unknown")
                    dt = datetime.fromtimestamp(timestamp)
                    date_time = dt.strftime(
                        "%B %d, %Y at %I:%M %p"
                    )  # "January 24, 2026 at 03:30 PM"
                    st.caption(f"Created: {date_time}")

                    description = model["ai_description"]
                    minimized_description = (
                        description[:200] + "..."
                        if len(description) > 200
                        else description
                    )
                    st.write(f"**{minimized_description}**")

                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{model['id']}"):
                        delete_ar_experience(
                            st.session_state["user"]["username"], model["id"]
                        )
                        st.success(f"Deleted '{model['topic']}'")
                        st.rerun()

                if st.button(
                    "View AR Model",
                    key=f"view_model_{model['id']}",
                    type="primary",
                    icon="👀",
                ):
                    st.session_state["generated_ar"] = True
                    st.session_state["topic"] = model["topic"]
                    st.session_state["sketchfab_embed_html"] = model[
                        "sketchfab_embed_html"
                    ]
                    st.session_state["ai_description"] = model["ai_description"]
                    st.session_state["model_viewer_html"] = model.get(
                        "model_viewer_html"
                    )
                    st.session_state["scroll_to_top"] = True
                    st.rerun()

                if i != len(ar_data) - 1:
                    "---"

        else:
            st.info("No AR models found. Create your first one!")

else:
    st.title(f"AR Experience - :blue[{st.session_state["topic"]}]")
    "---"

    # Generating the AR experience if not generated before
    if not st.session_state.get("sketchfab_embed_html"):
        with st.spinner("Generating your AR experience...", show_time=True):
            generate_ar_experience(
                st.session_state["topic"], st.session_state["show_in_ar"]
            )

    else:
        # Displaying the previously generated model's data
        height = 200 if st.session_state["device_supports_ar"] else 700
        components.html(st.session_state["sketchfab_embed_html"], height=height)
        "---"

        if st.session_state.get("ai_description"):
            st.markdown(st.session_state["ai_description"])
            "---"

        if st.session_state.get("model_viewer_html"):
            components.html(st.session_state["model_viewer_html"], height=50)
            "---"

    col1, col2 = st.columns(2)

    # Saving the AR model
    if col1.button("Save To History", icon="📂", use_container_width=True) or (
        st.session_state.get("save_after_auth")
        and st.session_state["topic"]
        and st.session_state["sketchfab_embed_html"]
        and st.session_state["ai_description"]
    ):
        st.session_state["save_after_auth"] = False

        if not st.session_state.get("user"):

            @st.dialog("Get Started")
            def sign_in_offer():
                st.info("Sign In to start saving your history!")
                col1, col2 = st.columns(2)

                if col1.button(
                    "Sign In",
                    icon="🔐",
                    use_container_width=True,
                ):
                    st.session_state["save_after_auth"] = True
                    st.session_state["page_before_auth"] = "ar"
                    st.switch_page("pages/signin.py")

                if col2.button(
                    "Create Account",
                    type="primary",
                    icon="👤",
                    use_container_width=True,
                ):
                    st.session_state["save_after_auth"] = True
                    st.session_state["page_before_auth"] = "ar"
                    st.switch_page("pages/signup.py")

            sign_in_offer()

        else:
            with st.spinner("Saving the AR model...", show_time=True):
                save_ar_experience(
                    st.session_state["user"]["username"],
                    st.session_state["topic"],
                    st.session_state["sketchfab_embed_html"],
                    st.session_state["ai_description"],
                    st.session_state.get("model_viewer_html", None),
                )
            st.success("AR model saved successfuly.")

    # "Generate A New AR Experience" button
    if col2.button(
        "Generate A New AR Experience",
        type="primary",
        icon="✨",
        use_container_width=True,
    ):
        del st.session_state["sketchfab_embed_html"]

        if st.session_state.get("ai_description"):
            del st.session_state["ai_description"]

        if st.session_state.get("model_viewer_html"):
            del st.session_state["model_viewer_html"]

        st.session_state["generated_ar"] = False
        st.session_state["scroll_to_top"] = True
        st.rerun()
