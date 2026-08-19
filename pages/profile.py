import streamlit as st
import time

# Set page config
st.set_page_config(
    page_title="Profile - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

cookies = st.session_state["cookies"]

if st.button("Sign Out"):
    auth_cookie_name = st.secrets["cookies"]["AUTH_NAME"]
    user_uid_cookie_name = st.secrets["cookies"]["USER_UID_NAME"]

    cookies[auth_cookie_name] = ""
    cookies[user_uid_cookie_name] = ""

    cookies.save()

    time.sleep(0.5)

    st.logout()