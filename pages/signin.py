import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import uuid
import time
from datetime import datetime
from typing import Literal
from services.account.auth import Login, ForgotPassword

# Set page config
st.set_page_config(
    page_title="Sign In - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

# ---------------------------------------------------------
# INITIALIZE BACKEND
# ---------------------------------------------------------

sender_email = st.secrets["smtp"]["SENDER_EMAIL"]
sender_app_password = st.secrets["smtp"]["SENDER_APP_PASSWORD"]

login = Login(st.session_state["root_ref"], sender_email, sender_app_password)

forgot_password = ForgotPassword(
    st.session_state["root_ref"],
    sender_email,
    sender_app_password,
)
cookies = st.session_state["cookies"]

# ---------------------------------------------------------
# CONSTANTS & STEP CONFIGURATION
# ---------------------------------------------------------

STEP_METHOD = "method"
STEP_EMAIL = "email"
STEP_VERIFY = "verification"
STEP_SUCCESS = "success"

VALID_STEPS = [
    STEP_METHOD,
    STEP_EMAIL,
    STEP_VERIFY,
    STEP_SUCCESS,
]

# ---------------------------------------------------------
# SESSION STATES INITIALIZATION
# ---------------------------------------------------------

if "login_step" not in st.session_state:
    st.session_state["login_step"] = STEP_METHOD

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------


def reset_signup():
    """Reset all login session states"""
    st.session_state["login_step"] = STEP_METHOD
    st.session_state["signup_username"] = ""
    st.session_state["signup_info"] = {}
    st.session_state["signup_user_uid"] = None
    st.query_params.clear()


def navigate_to(step: str):
    st.session_state["login_step"] = step
    st.rerun()


def subtitle_markdown(subtitle: str, align: str = "center"):
    # Subtitle
    st.markdown(
        f"""
        <h6 style='color: #2563EB; text-align: {align};'>
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


def reset_forgot_password():
    """Reset forgot password state"""
    st.session_state["forgot_pwd_step"] = None
    st.session_state["forgot_pwd_username"] = None
    st.session_state["forgot_pwd_email"] = None
    st.session_state["forgot_pwd_otp"] = None


def methods_icons_css(icon_url: str, button_key: Literal["google_btn", "email_btn"]):
    size = "24px"
    left_padding = "15px"
    if button_key == "email_btn":
        size = "28px"
        left_padding = "13px"

    st.html(f"""
        <style>
        div.st-key-{button_key} button {{
            padding-top: 8px !important;
            padding-bottom: 8px !important;
            transition: background-color 0.1s;
        }}

        div.st-key-{button_key} button p {{
            font-size: 16px !important;
            font-weight: 600 !important;
        }}

        div.st-key-{button_key} button::before {{
            content: "";
            position: absolute;
            left: {left_padding};
            top: 50%;
            transform: translateY(-50%);
            width: {size};
            height: {size};
            background-image: url('{icon_url}');
            background-repeat: no-repeat;
            background-size: contain;
            
        }}
        </style>
        """)


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
# STEP 0 — CHOOSE LOGIN METHOD
# ---------------------------------------------------------


def choose_method():
    st.title("👋 Welcome Back", anchor=False)
    " "

    # Apply custom CSS to attach icons to the methods
    email_key = "email_btn"
    google_key = "google_btn"

    methods_icons_css(
        icon_url=(
            "data:image/svg+xml;base64,"
            "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciICB2aWV3Qm94PSIwIDAgNDg"
            "gNDgiIHdpZHRoPSI0OHB4IiBoZWlnaHQ9IjQ4cHgiPjxwYXRoIGZpbGw9IiMxZTg4ZTUiIGQ9Ik"
            "0zNCw0MkgxNGMtNC40MTEsMC04LTMuNTg5LTgtOFYxNGMwLTQuNDExLDMuNTg5LTgsOC04aDIwY"
            "zQuNDExLDAsOCwzLjU4OSw4LDh2MjAgQzQyLDM4LjQxMSwzOC40MTEsNDIsMzQsNDJ6Ii8+PHBh"
            "dGggZmlsbD0iI2ZmZiIgZD0iTTM1LjkyNiwxNy40ODhMMjkuNDE0LDI0bDYuNTExLDYuNTExQzM"
            "1Ljk2OSwzMC4zNDcsMzYsMzAuMTc4LDM2LDMwVjE4IEMzNiwxNy44MjIsMzUuOTY5LDE3LjY1My"
            "wzNS45MjYsMTcuNDg4eiBNMjYuNjg4LDIzLjg5OWw3LjgyNC03LjgyNUMzNC4zNDcsMTYuMDMxL"
            "DM0LjE3OCwxNiwzNCwxNkgxNCBjLTAuMTc4LDAtMC4zNDcsMC4wMzEtMC41MTIsMC4wNzRsNy44"
            "MjQsNy44MjVDMjIuNzk1LDI1LjM4LDI1LjIwNSwyNS4zOCwyNi42ODgsMjMuODk5eiBNMjQsMjc"
            "uMDA5IGMtMS40NCwwLTIuODczLTAuNTQyLTMuOTktMS42MDVsLTYuNTIyLDYuNTIyQzEzLjY1My"
            "wzMS45NjksMTMuODIyLDMyLDE0LDMyaDIwYzAuMTc4LDAsMC4zNDctMC4wMzEsMC41MTItMC4wN"
            "zRsLTYuNTIyLTYuNTIyIEMyNi44NzMsMjYuNDY3LDI1LjQ0LDI3LjAwOSwyNCwyNy4wMDl6IE0x"
            "Mi4wNzQsMTcuNDg4QzEyLjAzMSwxNy42NTMsMTIsMTcuODIyLDEyLDE4djEyYzAsMC4xNzgsMC4"
            "wMzEsMC4zNDcsMC4wNzQsMC41MTIgTDE4LjU4NiwyNEwxMi4wNzQsMTcuNDg4eiIvPjwvc3ZnPg"
            "=="
        ),
        button_key=email_key,
    )
    methods_icons_css(
        icon_url="https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg",
        button_key=google_key,
    )

    if st.button(
        "**Continue with Email**",
        key=email_key,
        use_container_width=True,
    ):
        navigate_to(STEP_EMAIL)

    if st.button("**Continue with Google**", key=google_key, use_container_width=True):
        start = time.time()
        cookies["google_auth_clicked_at"] = datetime.now().isoformat()
        cookies.save()
        print(f"COOKIES: {time.time() - start}")
        time.sleep(0.15)

        st.login()

    " "
    if st.button(
        "**Don't have an account? :blue[Sign Up]**",
        type="tertiary",
        use_container_width=True,
    ):
        st.switch_page("pages/signup.py")


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

        if not email:
            st.error("❌ Email required")
            st.stop()

        validation = login.email_matches(email)

        if not validation:
            error_ph.error("This email is not registered.")
            st.session_state["show_signup_offer"] = True

        else:
            # Save the user_uid in session state
            st.session_state["login_user_uid"] = validation

            # Send verification code
            with error_ph.spinner("Sending code..."):
                login.send_otp(email)

            st.session_state["last_resend_time"] = time.time()

            # Save email for following steps
            st.session_state["login_email"] = email

            # Move to OTP verification
            navigate_to(STEP_VERIFY)

    if st.session_state.get("show_signup_offer", False):
        # Center the button AND increase its font-size to 16px
        st.html("""
            <style>
            .st-key-signup_offer_btn {
                display: flex !important;
                justify-content: center !important;
                width: 100% !important;
            }

            .st-key-signup_offer_btn div[data-testid="stMarkdownContainer"] p {
                font-size: 16px !important;
            }
            </style>
        """)

        if st.button(
            "New here? :blue[Create an account to get started.]",
            key="signup_offer_btn",
            type="tertiary",
        ):
            st.session_state["show_signup_offer"] = False
            st.switch_page("pages/signup.py")


# ---------------------------------------------------------
# STEP 2 — EMAIL VERIFICATION
# ---------------------------------------------------------


def verify_email():

    email: str = st.session_state["login_email"]

    header_and_navigation_row(
        STEP_EMAIL,
        "Verify your email",
        f"We sent a 6-digit verification code to<br><b>{email}</b>",
    )

    with st.form("email_verification_form", border=False):

        otp = st.text_input(
            "Verification code",
            placeholder="Enter the 6-digit code",
            label_visibility="collapsed",
            icon="🔐",
            max_chars=6,
        )

        status_ph = st.empty()

        submitted = st.form_submit_button(
            "Continue",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        otp = otp.strip()

        if not otp:
            status_ph.error("❌ Verification code required")
            return

        validation = login.validate_otp(email, otp)

        if validation is not True:
            status_ph.error(f"❌ {validation}")
            return

        status_ph.success("Login successful. Good to see you!")

        # Save cookies
        auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
        user_uid_cookie_name = st.secrets["cookies"]["USER_UID_NAME"]

        cookies[auth_cookie_name] = str(uuid.uuid4())
        cookies[user_uid_cookie_name] = st.session_state["login_user_uid"]
        cookies.save()

        time.sleep(1)

        # Redirect back to the home page
        st.switch_page("pages/home.py")

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
            login.send_otp(email)
            st.session_state["last_resend_time"] = time.time()
            st.toast("Verification code sent!", icon="📩")


# ---------------------------------------------------------
# FORGOT PASSWORD PAGES FUNCTIONS
# ---------------------------------------------------------


def forgot_pwd_email():
    st.title("🔑 Reset Password", anchor=False)
    " "

    id = st.text_input(
        "Email or Username",
        placeholder="Email or Username",
        label_visibility="collapsed",
        icon="📧",
    )

    status_ph = st.empty()
    " "

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Send Reset Code", type="primary", use_container_width=True):
            if not id.strip():
                status_ph.error("❌ Please enter your email or username.")
            else:
                user_uid, username, user_email = forgot_password.find_user_by_id(
                    id.strip()
                )

                # Show generic message (security: don't reveal if account exists)
                status_ph.info(
                    "✅ If this account exists, you'll receive a reset code via email"
                )

                if user_uid and user_email:
                    forgot_password.send_reset_otp(user_uid, username, user_email)
                    # st.session_state["forgot_pwd_username"] = username
                    st.session_state["forgot_pwd_user_uid"] = user_uid
                    st.session_state["forgot_pwd_email"] = user_email
                    time.sleep(0.5)

                st.session_state["forgot_pwd_step"] = "otp"
                st.rerun()

    with col2:
        if st.button(
            "🔙 Back to Sign In",
            type="tertiary",
            use_container_width=True,
        ):
            reset_forgot_password()
            st.rerun()


def forgot_pwd_otp():
    st.title("✨ Verify Code", anchor=False)
    " "

    st.markdown("##### Enter the 6-digit code sent to your email.")
    " "

    otp = st.text_input(
        "Reset Code",
        placeholder="000000",
        label_visibility="collapsed",
        icon="🔐",
        max_chars=6,
    )

    status_ph = st.empty()
    " "

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Verify Code", type="primary", use_container_width=True):
            if not otp or len(otp) != 6:
                status_ph.error("❌ Please enter a 6-digit code")
            else:
                if st.session_state.get("forgot_pwd_username"):
                    validation = forgot_password.validate_reset_otp(
                        st.session_state.get("forgot_pwd_user_uid"), otp
                    )

                    if validation is True:
                        st.session_state["forgot_pwd_otp"] = otp
                        st.session_state["forgot_pwd_step"] = "reset"
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        status_ph.error(f"❌ {validation}")
                else:
                    status_ph.error("❌ Invalid OTP")

    with col2:
        if st.button(
            "🔙 Back",
            type="tertiary",
            use_container_width=True,
        ):
            st.session_state["forgot_pwd_step"] = "email"
            st.rerun()


def forgot_pwd_reset_pwd():
    st.title("🔐 Create New Password", anchor=False)
    " "

    new_password = st.text_input(
        "New Password",
        type="password",
        placeholder="Enter your new password",
        label_visibility="collapsed",
        icon="🔏",
    )

    password_confirm = st.text_input(
        "Confirm Password",
        type="password",
        placeholder="Confirm your new password",
        label_visibility="collapsed",
        icon="🔏",
    )

    status_ph = st.empty()
    " "

    if st.button("Reset Password", type="primary", use_container_width=True):
        # Validate password
        validation = forgot_password.validate_password(new_password)
        if validation is not True:
            status_ph.error(f"❌ {validation}")
        elif new_password != password_confirm:
            status_ph.error("❌ Passwords do not match")
        else:
            # Reset the password
            if forgot_password.reset_password_with_otp(
                st.session_state.get("forgot_pwd_user_uid", ""),
                st.session_state.get("forgot_pwd_otp"),
                new_password,
            ):
                status_ph.success("✅ Password reset successful!")

                time.sleep(2)
                reset_forgot_password()
                st.rerun()
            else:
                status_ph.error("❌ Failed to reset password")

    " "
    if st.button("🔙 Back", use_container_width=True):
        reset_forgot_password()
        st.rerun()


# ---------------------------------------------------------
# PAGE ROUTER
# ---------------------------------------------------------


step = st.session_state["login_step"]

if step == STEP_METHOD:
    choose_method()

elif step == STEP_EMAIL:
    enter_email()

elif step == STEP_VERIFY:
    verify_email()
