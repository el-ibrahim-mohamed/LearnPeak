import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import uuid
import json
from datetime import datetime, timedelta
from account.auth import Login

# cookie_manager: stx.CookieManager = st.session_state["cookie_manager"]

with st.container(border=False):
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
        ":blue[Forgot password]", type="tertiary", use_container_width=True
    )
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
            username, user_info = login_result

            if remember_me:
                cookies = st.session_state["cookies"]

                auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
                uname_cookie_name = st.secrets["cookies"]["UNAME_NAME"]
                new_token = str(uuid.uuid4())
                expires_at = (datetime.now() + timedelta(days=30)).isoformat()

                cookies[auth_cookie_name] = json.dumps(
                    {
                        "token": new_token,
                        "expires_at": expires_at,
                    }
                )
                cookies[uname_cookie_name] = json.dumps(
                    {
                        "username": username,
                        "expires_at": expires_at,
                    }
                )
                cookies.save()

            st.session_state["user"] = {**user_info, "username": username}

            ph.success("✅ Login Successful")

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

    " "
    if st.button(
        "**Don't have an account? :blue[Sign Up]**",
        type="tertiary",
        use_container_width=True,
    ):
        st.switch_page("pages/signup.py")
