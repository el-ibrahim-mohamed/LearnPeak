import streamlit as st
import uuid
import time
from datetime import datetime
from services.account.auth import Signup

st.set_page_config(
    page_title="Sign Up • LearnPeak",
    page_icon="⛰️",
    layout="centered",
)

# ---------------------------------------------------------
# CONSTANTS & STEP CONFIGURATION
# ---------------------------------------------------------

STEP_METHOD = "method"
STEP_EMAIL = "email"
STEP_VERIFY = "verification"
STEP_USERNAME = "username"
STEP_INFO = "info"
STEP_SUCCESS = "success"

VALID_STEPS = [
    STEP_METHOD,
    STEP_EMAIL,
    STEP_VERIFY,
    STEP_USERNAME,
    STEP_INFO,
    STEP_SUCCESS,
]

# ---------------------------------------------------------
# SESSION STATES INITIALIZATION
# ---------------------------------------------------------

if "signup_step" not in st.session_state:
    st.session_state["signup_step"] = STEP_METHOD

if "signup_email" not in st.session_state:
    st.session_state["signup_email"] = ""

if "email_verified" not in st.session_state:
    st.session_state["email_verified"] = False

if "signup_username" not in st.session_state:
    st.session_state["signup_username"] = ""

if "signup_info" not in st.session_state:
    st.session_state["signup_info"] = {}

if "signup_user_uid" not in st.session_state:
    st.session_state["signup_user_uid"] = None

# ---------------------------------------------------------
# INITIALIZE BACKEND
# ---------------------------------------------------------

sender_email = st.secrets["smtp"]["SENDER_EMAIL"]
sender_app_password = st.secrets["smtp"]["SENDER_APP_PASSWORD"]

signup = Signup(
    st.session_state["root_ref"],
    sender_email,
    sender_app_password,
)

cookies = st.session_state["cookies"]

# ---------------------------------------------------------
# GOOGLE - TAKE USER INFO
# ---------------------------------------------------------

if st.session_state.get("take_signup_info"):
    # If the redirect handler already saved the Google email, use it.
    if st.session_state.get("signup_email"):
        st.session_state["email_verified"] = True
        st.session_state["username_from_google"] = True
        st.session_state["signup_step"] = STEP_USERNAME
        st.query_params["step"] = "username"

        st.session_state["take_signup_info"] = False
        st.session_state["redirected_to_signup"] = True

# ---------------------------------------------------------
# HELPER & NAVIGATION FUNCTIONS
# ---------------------------------------------------------


def reset_signup():
    """Reset all signup state and query parameters."""
    st.session_state["signup_step"] = STEP_METHOD
    st.session_state["signup_email"] = ""
    st.session_state["email_verified"] = False
    st.session_state["signup_username"] = ""
    st.session_state["signup_info"] = {}
    st.session_state["signup_user_uid"] = None
    st.query_params.clear()


def navigate_to(step: str):
    """Update state, update URL query params, and trigger rerun."""
    st.session_state["signup_step"] = step
    # METHOD is the root, not a query param
    if step == STEP_METHOD:
        st.query_params.clear()
    else:
        st.query_params["step"] = step
    st.rerun()


def subtitle_markdown(subtitle: str):
    # Subtitle
    st.markdown(
        f"""
        <h6 style='color: #2563EB; text-align: center;'>
            {subtitle}
        </h6>
        """,
        unsafe_allow_html=True,
    )


def header_and_navigation_row(
    back_nav: str, title: str, subtitle: str, disable_back_btn: bool = False
):
    # Navigation and Title
    if st.session_state.get("user_device_type", "mobile") == "mobile":
        col1, col2 = st.columns(2)

        if col1.button(
            "Back", icon="🔙", use_container_width=True, disabled=disable_back_btn
        ):
            if back_nav == STEP_METHOD:
                reset_signup()
                st.rerun()
            else:
                navigate_to(back_nav)

        if col2.button("Reset", icon="🔄", use_container_width=True):
            reset_signup()
            st.rerun()

        st.title(title, text_alignment="center", anchor=False)

    else:
        col1, col2, col3 = st.columns([1, 5, 1], vertical_alignment="bottom")

        if col1.button("Back", icon="🔙"):
            if back_nav == STEP_METHOD:
                reset_signup()
                st.rerun()
            else:
                navigate_to(back_nav)

        col2.title(title, text_alignment="center", anchor=False)

        if col3.button("Reset", icon="🔄"):
            reset_signup()
            st.rerun()

    subtitle_markdown(subtitle)

    " "


def get_max_allowed_step() -> str:
    """Calculates the furthest step the user is allowed to access."""
    if st.session_state.get("signup_user_uid"):
        return STEP_SUCCESS
    if st.session_state.get("signup_username") and st.session_state.get(
        "email_verified"
    ):
        return STEP_INFO
    if st.session_state.get("email_verified"):
        return STEP_USERNAME
    if st.session_state.get("signup_email"):
        return STEP_VERIFY
    return STEP_EMAIL


def sync_and_validate_step():
    """Binds URL query parameters to session state and enforces access rules."""
    requested_step = st.query_params.get("step", STEP_METHOD)
    print(1, requested_step)

    if requested_step not in VALID_STEPS:
        requested_step = STEP_METHOD
    print(2, requested_step)

    max_allowed = get_max_allowed_step()
    print(3, max_allowed)

    requested_index = VALID_STEPS.index(requested_step)
    max_index = VALID_STEPS.index(max_allowed)
    print(4, requested_index)
    print(5, max_index)

    # Block access if trying to skip ahead via URL manipulation
    if requested_index > max_index:
        actual_step = max_allowed
    else:
        actual_step = requested_step
    print(6, actual_step)
    print()

    st.session_state["signup_step"] = actual_step

    if actual_step == STEP_METHOD:
        if "step" in st.query_params:
            st.query_params.clear()
    else:
        st.query_params["step"] = actual_step


# Run safety and state sync check on every execution
sync_and_validate_step()


# Hide the header anchor links via CSS
st.markdown(
    """
    <style>
    h6 a {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# STEP 0 — CHOOSE SIGNUP METHOD
# ---------------------------------------------------------


def choose_method():

    st.title("Welcome to LearnPeak 👋", text_alignment="center", anchor=False)

    subtitle_markdown(
        "Ready for your personal study space? Let’s get you set up in under a minute!"
    )

    " "

    _, col2, _ = st.columns([1, 4, 1])

    with col2:
        if st.button(
            "Continue with Email", key="email_btn", icon="✉️", use_container_width=True
        ):
            navigate_to(STEP_EMAIL)

        if st.button(
            "Continue with Google", key="google_btn", use_container_width=True
        ):
            start = time.time()
            cookies["google_auth_clicked_at"] = datetime.now().isoformat()
            cookies.save()
            print(f"COOKIES: {time.time() - start}")
            time.sleep(0.3)

            st.login()

    " "

    _, col2, _ = st.columns([3.2, 3, 3])

    if col2.button(
        "Already have an account?&thinsp; :blue[Sign in]",
        type="tertiary",
    ):
        st.switch_page("pages/signin.py")


# ---------------------------------------------------------
# STEP 1 — EMAIL
# ---------------------------------------------------------


def enter_email():

    header_and_navigation_row(
        STEP_METHOD, "Create your account", "Enter your email address to continue."
    )

    with st.form("signup_email_form", border=False):
        email = st.text_input(
            "Email",
            placeholder="Enter your email",
            label_visibility="collapsed",
            icon="📧",
        )
        error_ph = st.empty()

        submitted = st.form_submit_button(
            "Continue",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        email = email.strip().lower()

        validation = signup.validate_email(email)

        if validation is not True:
            error_ph.error(f"❌ {validation}")
            return

        # Send verification code
        with error_ph.spinner("Sending Code..."):
            signup.send_otp(email)

        st.session_state["last_resend_time"] = time.time()

        # Save email for following steps
        st.session_state["signup_email"] = email

        # Move to OTP verification
        navigate_to(STEP_VERIFY)


# ---------------------------------------------------------
# STEP 2 — EMAIL VERIFICATION
# ---------------------------------------------------------


def verify_email():

    email: str = st.session_state["signup_email"]

    header_and_navigation_row(
        STEP_EMAIL,
        "Verify your email",
        f"We sent a 6-digit verification code to<br><b>{email}</b>",
    )

    with st.form("email_verification_form", border=False):

        code = st.text_input(
            "Verification code",
            placeholder="Enter the 6-digit code",
            label_visibility="collapsed",
            icon="🔐",
            max_chars=6,
        )

        error_ph = st.empty()

        submitted = st.form_submit_button(
            "Continue",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        code = code.strip()

        if not code:
            error_ph.error("❌ Verification code required")
            return

        validation = signup.validate_otp(email, code)

        if validation is not True:
            error_ph.error(f"❌ {validation}")
            return

        st.session_state["email_verified"] = True
        navigate_to(STEP_USERNAME)

    # ---------------------------------------------------------
    # RESEND CODE (STATIC COOLDOWN)
    # ---------------------------------------------------------

    RESEND_COOLDOWN = 30

    if st.button("\u00a0:blue[Resend Code]", type="tertiary"):
        last_sent = st.session_state.get("last_resend_time", 0)
        elapsed = time.time() - last_sent

        if elapsed < RESEND_COOLDOWN:
            remaining = int(RESEND_COOLDOWN - elapsed)
            st.toast(
                f"Please wait :red[{remaining}s] before requesting a new code.",
                icon="⏳",
            )
        else:
            signup.send_otp(email)
            st.session_state["last_resend_time"] = time.time()
            st.toast("Verification code sent!", icon="📩")


# ---------------------------------------------------------
# STEP 3 — USERNAME
# ---------------------------------------------------------


def enter_username(
    from_google: bool = st.session_state.get("google_username_input", False)
):

    header_and_navigation_row(
        STEP_VERIFY,
        "Choose a Username",
        "This is how you'll be identified on LearnPeak.",
        disable_back_btn=from_google,
    )

    with st.form("signup_username_form", border=False):

        username = st.text_input(
            "Username",
            value=st.session_state.get("signup_username_placeholder", ""),
            placeholder="Choose a username",
            label_visibility="collapsed",
            icon="👤",
        )

        st.markdown(
            """
            <div style="color: #909298; font-size: 14px; line-height: 1.8; margin-top: -4px; margin-bottom: 12px; padding-left: 4px;">
                <span style="font-size: 16px; font-weight: bold;">•</span>&nbsp;&nbsp;At least 4 characters<br>
                <span style="font-size: 16px; font-weight: bold;">•</span>&nbsp;&nbsp;Letters, numbers, and underscores only
            </div>
            """,
            unsafe_allow_html=True,
        )

        error_ph = st.empty()

        submitted = st.form_submit_button(
            "Continue",
            type="primary",
            icon="⏭️",
            use_container_width=True,
        )

    if submitted:

        username = username.strip()

        validation = signup.validate_username(username)

        if validation is not True:
            error_ph.error(f"❌ {validation}")
            return

        st.session_state["signup_username"] = username
        navigate_to(STEP_INFO)

    " "


# ---------------------------------------------------------
# STEP 4 — USER INFORMATION
# ---------------------------------------------------------


def enter_user_info():

    header_and_navigation_row(
        STEP_USERNAME,
        "Tell us about yourself",
        "Enter some basic information to personalize your LearnPeak experience.",
    )

    grade_mapping = {
        "🎨 KG 1": "kg1",
        "🎨 KG 2": "kg2",
        "🎒 Primary 1": "prim1",
        "🎒 Primary 2": "prim2",
        "🎒 Primary 3": "prim3",
        "🎒 Primary 4": "prim4",
        "🎒 Primary 5": "prim5",
        "🎒 Primary 6": "prim6",
        "📓 Preparatory 1": "prep1",
        "📓 Preparatory 2": "prep2",
        "📓 Preparatory 3": "prep3",
        "🔬 Secondary 1": "sec1",
        "🔬 Secondary 2": "sec2",
        "🔬 Secondary 3": "sec3",
    }

    with st.form("signup_user_info_form", border=False):

        full_name = st.text_input(
            "Full name",
            value=st.session_state.get("signup_name_placeholder", ""),
            placeholder="Enter your full name",
            icon="👤",
        )

        country = st.selectbox(
            "🌍 Country",
            options=["Egypt"],
            placeholder="Enter your country",
        )

        education = st.selectbox(
            "🎓 Education",
            options=["National"],
            placeholder="Enter your school / educational system",
        )

        grade_display = st.selectbox(
            "Grade",
            list(grade_mapping.keys()),
        )
        " "
        error_ph = st.empty()

        submitted = st.form_submit_button(
            "Create account",
            type="primary",
            icon="🚀",
            use_container_width=True,
        )

    if submitted:

        if not full_name.strip():
            error_ph.error("Full name required")
            return

        if not country.strip():
            error_ph.error("Country required")
            return

        if not education.strip():
            error_ph.error("Education required")
            return

        grade = grade_mapping[grade_display]

        email = st.session_state["signup_email"]
        username = st.session_state["signup_username"]

        try:
            user_uid = signup.register_email_account(
                email=email,
                username=username,
                full_name=full_name.strip(),
                country=country.lower(),
                education=education.lower(),
                grade=grade,
            )

            st.session_state["signup_user_uid"] = user_uid

        except Exception as e:
            error_ph.error("Something went wrong while creating your account.")
            st.write(f"Signup error: {e}")
            return

        # Account successfully created
        navigate_to(STEP_SUCCESS)


# ---------------------------------------------------------
# STEP 5 — SUCCESS
# ---------------------------------------------------------


def signup_success():
    # Save cookies
    auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
    user_uid_cookie_name = st.secrets["cookies"]["USER_UID_NAME"]

    cookies[auth_cookie_name] = str(uuid.uuid4())
    print(f"USER UID: {st.session_state["signup_user_uid"]}")
    cookies[user_uid_cookie_name] = st.session_state["signup_user_uid"]
    cookies.save()

    st.title("Account created! 🎉", text_alignment="center")
    st.markdown(
        """
        <h6 style='color: #00A86B; text-align: center;'>
            Welcome to LearnPeak. Your account has been created successfully.
        </h6>
        """,
        unsafe_allow_html=True,
    )
    st.balloons()
    " "

    if st.button(
        "Go to home page",
        type="primary",
        icon="🏠",
        use_container_width=True,
    ):
        st.switch_page("pages/home.py")


# ---------------------------------------------------------
# PAGE ROUTER
# ---------------------------------------------------------

step = st.session_state["signup_step"]

if step == STEP_METHOD:
    choose_method()

elif step == STEP_EMAIL:
    enter_email()

elif step == STEP_VERIFY:
    verify_email()

elif step == STEP_USERNAME:
    enter_username()

elif step == STEP_INFO:
    enter_user_info()

elif step == STEP_SUCCESS:
    signup_success()
