import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import time
from typing import Literal
from account.auth import Signup


def email_login():
    st.title("Enter Your Email and a Password", text_alignment="center")
    " "
    with st.form("email_signup", border=False):
        email = st.text_input(
            "Email",
            key="email_input",
            placeholder="Email",
            label_visibility="collapsed",
            icon="📧",
        )
        email_ph = st.empty()

        password = st.text_input(
            "Password",
            key="password_input",
            type="password",
            placeholder="Create a strong password",
            label_visibility="collapsed",
            icon="🔏",
        )
        password_ph = st.empty()

        " "
        if (
            st.form_submit_button(
                "Continue", type="primary", icon="⏭️", use_container_width=True
            )
            and email
            and password
        ):
            email_validity = signup.validate_email(email)
            if email_validity != True:
                email_ph.error(email_validity)

            password_validity = signup.validate_password(password)
            if password_validity != True:
                password_ph.error(password_validity)

            if email_validity == True and password_validity == True:
                st.session_state["new_user"] = {
                    "email": email.strip(),
                    "password": password.strip(),
                }
                st.session_state["signup_step"] = 2
                st.rerun()


def verify_email():
    user = st.session_state["new_user"]
    email = user["email"]

    if not st.session_state.get("verification_code"):
        verification_code = signup.send_verification_code(email)
        st.session_state["verification_code"] = verification_code

    st.title("Verify your email address", text_alignment="center")
    " "
    st.markdown(
        f"<h6 style='color: #4A4A4A;'>We sent a 6-digit verification code to {email}. Enter the code below to confirm your email address.</h6>",
        unsafe_allow_html=True,
        text_alignment="center",
    )

    with st.form("email_verification", border=False):
        code = st.text_input("Code", placeholder="Enter the 6-digit code")
        code_ph = st.empty()
        " "

        if st.form_submit_button(
            "Continue", type="primary", icon="⏭️", use_container_width=True
        ):
            code_valid = signup.validate_verification_code(email, code)
            if code_valid != True:
                code_ph.error(code_valid)
            else:
                st.session_state["signup_step"] = 3
                st.rerun()


def take_username():
    st.title("Choose a username", text_alignment="center")
    " "

    with st.form("take_username", border=False):
        username = st.text_input(
            "Username",
            placeholder="Choose a username",
            label_visibility="collapsed",
            icon="👤",
        )
        uname_ph = st.empty()
        st.write(
            """
- At least 4 characters long
- Only letters, numbers, and underscores
"""
        )
        " "

        if (
            st.form_submit_button(
                "Continue", type="primary", icon="⏭️", use_container_width=True
            )
            and username
        ):
            username_validity = signup.validate_username(username)

            if username_validity != True:
                uname_ph.error(username_validity)
            else:
                new_user: dict = st.session_state.get("new_user", {})
                new_user["username"] = username
                st.session_state["new_user"] = new_user

                st.session_state["signup_step"] = 4
                st.rerun()


def take_user_info():

    def map_grades(grade: str, to: Literal["short", "long"] = "short"):
        grade_mapping = {
            "🎨 kG 1": "kg1",
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

        if to == "short":
            return grade_mapping[grade]

        elif to == "long":
            return [k for k, v in grade_mapping.items() if v == "prim1"][0]

    st.title("Let us know more about you", text_alignment="center")
    st.markdown(
        "<h6 style='color: #4A4A4A;'>Enter your basic learning information.</h6>",
        unsafe_allow_html=True,
        text_alignment="center",
    )
    " "

    with st.form("take_user_info", border=False):
        full_name = st.text_input("Full name", placeholder="e.g. Mohamed Salah")
        " "
        col1, col2 = st.columns(2)
        country = col1.selectbox(
            "🏡 Country", ["Egypt"], placeholder="Choose your country"
        )
        education = col2.selectbox(
            "🎓 Education", ["National"], placeholder="Choose your education system"
        )

        grades = [
            "🎨 kG 1",
            "🎨 KG 2",
            "🎒 Primary 1",
            "🎒 Primary 2",
            "🎒 Primary 3",
            "🎒 Primary 4",
            "🎒 Primary 5",
            "🎒 Primary 6",
            "📓 Preparatory 1",
            "📓 Preparatory 2",
            "📓 Preparatory 3",
            "🔬 Secondary 1",
            "🔬 Secondary 2",
            "🔬 Secondary 3",
        ]
        grade = st.selectbox(
            "📝 Grade", grades, index=None, placeholder="Choose your grade"
        )
        " "

        ph = st.empty()
        if (
            st.form_submit_button(
                "Create Account", type="primary", icon="⏭️", use_container_width=True
            )
            and full_name
            and country
            and education
            and grade
        ):
            ph.success(
                "Created your account successfully. Welcome to **LearnPeak**!"
            )

            new_user = st.session_state["new_user"]
            new_user["full_name"] = full_name
            new_user["country"] = country.lower()
            new_user["education"] = education.lower()
            new_user["grade"] = map_grades(grade)

            signup.signup_user(**new_user)
            st.session_state["user"] = new_user
            st.session_state["new_user"] = {}
            time.sleep(1)

            # Save something to history after auth Logic
            if st.session_state.get("save_after_auth"):
                pages_map = {"ar": "pages/ar.py", "quizzes": "pages/quizzes.py"}
                page_path = pages_map[st.session_state["page_before_auth"]]
                st.session_state["scroll_to_bottom"] = True
                st.switch_page(page_path)
            else:
                st.switch_page("pages/home.py")


# st.session_state["signup_method"] = "email"

if not st.session_state.get("signup_method"):
    st.title("Create your :red[Learn] :blue[Peak] account", text_alignment="center")
    _, col2, _ = st.columns(3)
    col2.image("static/logo.png")
    " "

    btn1_ph = st.empty()
    btn2_ph = st.empty()
    btn3_ph = st.empty()

    # Continue with Email
    with stylable_container(
        key="email_button",
        css_styles="""
            div[data-testid="stButton"] > button {
                background-color: #6ea649 !important;
                color: white !important;
                border-radius: 10px !important;
                padding: 0.6em 1em !important;
            }

            div[data-testid="stButton"] > button p {
                font-size: 18px !important;
                font-weight: 700 !important;
            }
        """,
    ):
        if st.button("Continue with Email", icon="✉️", use_container_width=True):
            st.session_state["signup_method"] = "email"
            st.session_state["signup_step"] = 1
            st.rerun()

    # # OR Divider
    # st.markdown(
    #     """
    # <style>
    # .divider {
    #     display: flex;
    #     align-items: center;
    #     text-align: center;
    #     margin: 25px 0;
    # }

    # .divider::before,
    # .divider::after {
    #     content: "";
    #     flex: 1;
    #     border-bottom: 1px solid #d9d9d9;
    # }

    # .divider:not(:empty)::before {
    #     margin-right: 15px;
    # }

    # .divider:not(:empty)::after {
    #     margin-left: 15px;
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

    # # Continue with Google
    # with stylable_container(
    #     key="google_button",
    #     css_styles="""
    #         div[data-testid="stButton"] > button {
    #             background-color: #4285F4 !important;
    #             color: white !important;
    #             border-radius: 10px !important;
    #             padding: 0.6em 1em !important;
    #         }
    #     """,
    # ):
    #     if st.button("Continue with Google", use_container_width=True):
    #         st.session_state["signup_method"] = "google"
    #         st.rerun()

    " "
    _, col2, _ = st.columns([3, 4, 3])
    if col2.button("Already have an account? :blue[Sign In]", type="tertiary"):
        st.switch_page("pages/signin.py")

else:
    if st.session_state["signup_method"] == "email":
        sender_email = st.secrets["smtp"]["SENDER_EMAIL"]
        sender_app_password = st.secrets["smtp"]["SENDER_APP_PASSWORD"]
        signup = Signup(st.session_state["root_ref"], sender_email, sender_app_password)

        if st.session_state["signup_step"] == 1:
            email_login()

        elif st.session_state["signup_step"] == 2:
            verify_email()

        elif st.session_state["signup_step"] == 3:
            take_username()

        elif st.session_state["signup_step"] == 4:
            take_user_info()
