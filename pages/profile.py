import streamlit as st

cookies = st.session_state["cookies"]
if st.button("Sign Out"):
    st.session_state["USER_UID_NAME"] = ""
    cookies["AUTH_NAME"] = ""
    cookies.save()
    st.rerun()