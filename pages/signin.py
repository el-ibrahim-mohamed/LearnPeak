import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import uuid
import time
from services.account.auth import Login, ForgotPassword


# Define Helper functions
def reset_forgot_password():
    """Reset forgot password state"""
    st.session_state["forgot_pwd_step"] = None
    st.session_state["forgot_pwd_username"] = None
    st.session_state["forgot_pwd_email"] = None
    st.session_state["forgot_pwd_otp"] = None


# MAIN UI
with st.container(border=False):
    # Init ForgotPassword once
    forgot_password = ForgotPassword(
        st.session_state["root_ref"],
        st.secrets["smtp"]["SENDER_EMAIL"],
        st.secrets["smtp"]["SENDER_APP_PASSWORD"],
    )

    # FORGOT PASSWORD - STEP 1: EMAIL/USERNAME INPUT
    if st.session_state.get("forgot_pwd_step") == "email":
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
                    user_uid, username, user_email = forgot_password.find_user_by_id(id.strip())

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

    # FORGOT PASSWORD - STEP 2: OTP VERIFICATION
    elif st.session_state.get("forgot_pwd_step") == "otp":
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

    # FORGOT PASSWORD - STEP 3: NEW PASSWORD
    elif st.session_state.get("forgot_pwd_step") == "reset":
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

    # LOGIN SCREEN
    else:
        st.title("👋 Welcome Back", anchor=False)
        " "
        " "
        email_or_uname = st.text_input(
            "Username",
            placeholder="Username or Email",
            label_visibility="collapsed",
            icon="📧",
        )
        uname_ph = st.empty()
        " "
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Password",
            label_visibility="collapsed",
            icon="🔏",
        )
        pwd_ph = st.empty()

        col1, _, col2 = st.columns([4, 3, 2])
        remember_me = col1.checkbox("Remember me")
        forgot_pwd = col2.button(
            ":blue[Forgot password?]", type="tertiary", use_container_width=True
        )

        if forgot_pwd:
            st.session_state["forgot_pwd_step"] = "email"
            st.rerun()

        ph = st.empty()

        " "
        if (
            st.button(
                "Sign In",
                type="primary",
                use_container_width=True,
            )
            and email_or_uname
            and password
        ):
            login = Login(st.session_state["root_ref"])

            login_result = login.login(email_or_uname.strip(), password.strip())
            if login_result:
                user_uid, user_info = login_result

                if remember_me:
                    cookies = st.session_state["cookies"]

                    auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
                    user_uid_cookie_name = st.secrets["cookies"]["USER_UID_NAME"]

                    cookies[auth_cookie_name] = str(uuid.uuid4())
                    cookies[user_uid_cookie_name] = user_uid
                    cookies.save()

                st.session_state["user"] = user_info

                ph.success("✅ Login Successful")

                # Give browser time to save cookies before redirecting
                time.sleep(1.5)

                # Save something to history after auth logic OR redirect to home page
                if st.session_state.get("save_after_auth"):
                    pages_map = {"ar": "pages/ar.py", "quizzes": "pages/quizzes.py"}
                    page_path = pages_map[st.session_state["page_before_auth"]]
                    st.session_state["scroll_to_bottom"] = True
                    st.switch_page(page_path)
                else:
                    st.switch_page("pages/home.py")

            else:
                ph.error("❌ Username or Password Incorrect")

        " "
        if st.button(
            "**Don't have an account? :blue[Sign Up]**",
            type="tertiary",
            use_container_width=True,
        ):
            st.switch_page("pages/signup.py")

        # # OR Divider
        # st.markdown(
        #     """
        # <style>
        # .divider {
        #     display: flex;
        #     align-items: center;
        #     text-align: center;
        #     margin-top: 5px;
        #     margin-bottom: 20px;
        # }

        # .divider::before,
        # .divider::after {
        #     content: "";
        #     flex: 1;
        #     border-bottom: 1px solid #d9d9d9;
        # }

        # .divider:not(:empty)::before {
        #     margin-right: 20px;
        # }

        # .divider:not(:empty)::after {
        #     margin-left: 20px;
        # }

        # .divider span {
        #     color: #888;
        #     font-size: 14px;
        #     font-weight: 500;
        # }
        # </style>

        # <div class="divider">
        #     <span>OR</span>
        # </div>
        # """,
        #     unsafe_allow_html=True,
        # )

        # with stylable_container(
        #     "continue_with_google",
        #     css_styles="""
        #     div.stButton > button {
        #         background-color: #4285F4;
        #         color: white;
        #     }""",
        # ):
        #     button2_clicked = st.button("Continue with Google", use_container_width=True)
