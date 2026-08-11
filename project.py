import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
from google import genai
import firebase_admin
from firebase_admin import credentials, db

st.set_page_config(
    "LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

def load_app():
    # --- Setting up Firebase RTDB ---
    @st.cache_resource
    def get_db_root():
        # Fetch the service account key JSON file contents
        service_account_key_dict = dict(st.secrets["firebase_service_account"])

        # Check if no default app is already initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_key_dict)
            firebase_admin.initialize_app(
                credential=cred,
                options={
                    "databaseURL": "https://learn-peak-88a91-default-rtdb.europe-west1.firebasedatabase.app",
                    "databaseAuthVariableOverride": {
                        "uid": st.secrets["firebase"]["UID"]
                    },
                },
            )

        return db.reference("/")

    root_ref = get_db_root()

    # --- Checking for auth cookies ---
    if "cookies" not in st.session_state:
        cookies = EncryptedCookieManager(
            password=st.secrets["cookies"]["PASSWORD"], prefix="learnpeak/"
        )
        if not cookies.ready():
            st.stop()

        st.session_state["cookies"] = cookies

    cookies: EncryptedCookieManager = st.session_state["cookies"]

    if not st.session_state.get("user") and cookies.get(
        st.secrets["cookies"]["AUTH_NAME"]
    ):
        user_uid = cookies.get(st.secrets["cookies"]["USER_UID_NAME"])
        user_info = root_ref.child(f"users/{user_uid}/info").get()
        st.session_state["user"] = {**user_info, "uid": user_uid}

    # --- Defining the app's pages with st.Page ---
    # Home
    home = st.Page("pages/home.py", title="Home", icon="🏠", default=True)

    # Account
    signin = st.Page("pages/signin.py", title="Sign In", icon="🔐")
    signup = st.Page("pages/signup.py", title="Create Account", icon="🚀")

    profile = st.Page("pages/profile.py", title="Profile", icon="🧑")

    # Tools
    ask_book = st.Page("pages/ask-book.py", title="Ask your book", icon="🧠")
    ar = st.Page("pages/ar.py", title="Learn with AR", icon="🪄")
    quizzes = st.Page("pages/quizzes.py", title="Quiz Generation", icon="📝")

    # --- Running the pages ---
    if st.session_state.get("user"):
        pages = {
            "": [home],
            "👤 Account": [profile],
            "✨ Features": [ask_book, ar, quizzes],
        }
    else:
        pages = {
            "": [home],
            "🚀 Get Started": [signin, signup],
            "✨ Features": [ask_book, ar, quizzes],
        }

    # Run st.navigation as soon as possible to show the nav to the user
    pg = st.navigation(pages, position="top")

    # Sharing session states
    if "client" not in st.session_state:

        @st.cache_resource
        def get_gemini_client():
            return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

        st.session_state["client"] = get_gemini_client()

    if "root_ref" not in st.session_state:
        st.session_state["root_ref"] = root_ref

    # Returning the pg to run
    return pg


if "app_loaded" not in st.session_state:
    with st.spinner("Loading LearnPeak"):
        pg = load_app()
        st.session_state["app_loaded"] = True
    pg.run()

else:
    pg = load_app()

    # Run time-consuming code after app load
    from streamlit_js_eval import streamlit_js_eval
    from user_agents import parse

    if "user_device_type" not in st.session_state:
        user_agent = streamlit_js_eval(
            js_expressions="window.navigator.userAgent", key="user_agent"
        )

        if user_agent:
            ua = parse(user_agent)

            if ua.is_mobile:
                st.session_state["user_device_type"] = "mobile"
            elif ua.is_tablet:
                st.session_state["user_device_type"] = "tablet"
            elif ua.is_pc:
                st.session_state["user_device_type"] = "pc"

    if "screen_inner_width" not in st.session_state:
        inner_width = streamlit_js_eval(
            js_expressions="window.innerWidth", key="inner_width"
        )

        if inner_width:
            st.session_state["screen_inner_width"] = inner_width

    pg.run()
