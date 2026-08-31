import streamlit as st
import uuid
import time
import re
from datetime import datetime
from services.account.auth import Login

# Set page config
about_text = """**LearnPeak** is an AI-powered learning platform built around students' school curricula and textbooks.

Instead of providing generic AI answers, LearnPeak is designed to understand the educational material students are actually expected to study. It combines AI-powered textbook conversations, quiz generation, summarization, interactive learning experiences, and science-backed study strategies to help students understand, practice, and retain their curriculum.

### What LearnPeak offers

- **Ask Your Book** — Ask questions about your textbook and get answers grounded in its content.
- **AI Quizzes** — Generate quizzes from curriculum material for active practice and revision.
- **Learn with AR** — Explore educational concepts through interactive 3D experiences.
- **Science-backed Study Strategies** — Learn and apply techniques such as spaced repetition and active recall.

LearnPeak's goal is to make studying more effective by combining **students' actual curriculum, artificial intelligence, and proven learning methods** in one platform.

Built with 💙 for students by a student.
"""

st.set_page_config(
    page_title="LearnPeak | AI Tools Built for Your Curriculum",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
    menu_items={
        "Report a Bug": "mailto:learnpeak.eg@gmail.com?subject=LearnPeak%20Bug%20Report",
        "About": about_text,
    },
)

if "page" in st.query_params:
    target_page = st.query_params["page"]
    print(target_page)
    st.query_params.clear()
    try:
        st.switch_page(f"pages/{target_page}.py")
    except Exception as e:
        print(e)
        pass

st.markdown(
    """
    <meta
        name="description"
        content="AI-powered learning system built around your curriculum, with textbook chat, quizzes, AR, and science-backed study strategies like spaced repetition for lasting knowledge.">
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# GOOGLE AUTH REDIRECT LOGIC
# ---------------------------------------------------------

# st.write(st.session_state.get("user"))
# st.write(st.user.is_logged_in)


def handle_google_auth_redirect():
    if (
        not st.session_state.get("user")
        and st.user.is_logged_in
        and not st.session_state.get("take_signup_info", False)
    ):
        login = Login(
            st.session_state["root_ref"],
            st.secrets["smtp"]["SENDER_EMAIL"],
            st.secrets["smtp"]["SENDER_APP_PASSWORD"],
        )
        cookies = st.session_state["cookies"]

        # Check auth state (if logged in)
        user_uid = login.email_matches(st.user["email"])

        # If logged in, save cookies, and user ss
        if user_uid:
            # Save cookies
            auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
            user_uid_cookie_name = st.secrets["cookies"]["USER_UID_NAME"]

            cookies[auth_cookie_name] = str(uuid.uuid4())
            cookies[user_uid_cookie_name] = user_uid
            cookies["google_auth_clicked_at"] = "no_redirect"

            cookies.save()
            time.sleep(0.2)

            st.logout()
            st.stop()

        else:
            redirect_to_signup = True

            # Detect if the user had skipped/abandoned the info form
            # So don't redirect to it anymore AND logout
            google_auth_clicked_at = cookies.get("google_auth_clicked_at")
            if google_auth_clicked_at:
                if google_auth_clicked_at == "no_redirect":
                    redirect_to_signup = False

                else:
                    time_difference = datetime.now() - datetime.fromisoformat(
                        google_auth_clicked_at
                    )
                    seconds_passed = time_difference.total_seconds()
                    if seconds_passed > 500:  # 5 minutes
                        redirect_to_signup = False

            if redirect_to_signup:
                st.session_state["take_signup_info"] = True

                cookies["google_auth_clicked_at"] = "no_redirect"
                cookies.save()

                signup_email = st.user.get("email")
                st.session_state["signup_email"] = signup_email
                st.session_state["email_verified"] = True

                signup_username_placeholder = signup_email.split("@")[0]
                signup_username_placeholder = re.sub(
                    r"[^\w]", "", signup_username_placeholder
                )
                st.session_state["signup_username_placeholder"] = (
                    signup_username_placeholder
                )

                st.session_state["signup_name_placeholder"] = st.user.get("name", "")

                st.switch_page("pages/signup.py")


handle_google_auth_redirect()


# ---------------------------------------------------------
# Home Page
# ---------------------------------------------------------

# --- 1. HERO SECTION ---
st.title("⛰️ :red[Learn]:blue[Peak]", text_alignment="center", anchor=False)
st.markdown(
    """
    <div style='font-size: 1.4rem; font-weight: 500;'>
        AI that understands your curriculum.
    </div>
    """,
    unsafe_allow_html=True,
    text_alignment="center",
)
st.space(20)

# Centered Hero Button
_, col2, _ = st.columns([0.1, 0.8, 0.1])
with col2:
    if st.button(
        "🚀 Start with Ask Your Book", use_container_width=True, type="primary"
    ):
        st.switch_page("pages/ask-book.py")

"---"

# --- 2. WHAT IS LEARNPEAK? ---
st.text(
    "AI-powered learning system built around your curriculum, with textbook chat, quizzes, AR, "
    "and science-backed study strategies to retain knowledge."
)

# --- 3. WHY LEARNPEAK? ---
st.subheader("Why LearnPeak?")

st.markdown(
    "- 🎯 **Tailored to Your Textbooks:** LearnPeak syncs directly with your actual curriculum, "
    "so you focus strictly on what’s on your exam—not generic learning content."
)
st.markdown(
    "- 🧠 **Study with Strategy:** Master proven learning techniques and let LearnPeak "
    "automatically structure your study sessions to put them into practice."
)
st.markdown(
    "- ⚡ **Interactive & Active Learning:** Test your knowledge with instant AI-generated "
    "quizzes and bring complex concepts to life with immersive AR."
)

"---"

# --- 4. FEATURES SECTION ---
st.subheader("Features")

col1, col2 = st.columns(2)

with col1.container(border=True):
    st.markdown("### 📚 Ask Your Book", anchors=False)
    st.write("Chat with your textbooks for instant, curriculum-based answers.")

    " "
    if st.button("Ask your book", use_container_width=True):
        st.switch_page("pages/ask-book.py")

with col2.container(border=True):
    st.markdown("### 📝 Quiz Generation", anchors=False)
    st.write("Turn lessons into custom practice quizzes in seconds.")

    " "
    if st.button("Generate Quiz", use_container_width=True):
        st.switch_page("quizzes.py")

" "
col1, col2 = st.columns(2)

with col1.container(border=True):
    st.markdown("### 🥽 Learn with AR", anchors=False)
    st.write("Explore complex topics using interactive 3D models.")

    " "
    if st.button("Launch AR", key="btn_ar", use_container_width=True):
        st.switch_page("pages/ar.py")

"---"

# --- 5. FOOTER ---
st.markdown("### :red[Learn]:blue[Peak]", text_alignment="center", anchors=False)
st.markdown(
    """
    <div style='font-size: 1rem; font-weight: 500;'>
        Master your curriculum with AI-powered study tools built directly around your textbooks.
    </div>
    """,
    unsafe_allow_html=True,
    text_alignment="center",
)
