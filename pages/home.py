import streamlit as st

with st.sidebar:
    if st.session_state.get("user"):
        full_name: str = st.session_state["user"]["full_name"]
        st.title(f"👋 Welcome back :blue[{full_name.split()[0]}]!")
    else:
        st.title("👋 Welcome to :red[Learn]:blue[Peak]!")

    " "
    st.write(
        "🔎 Explore our creative, AI-powered features to enhance your learning experience:"
    )
    st.write(
        """- 🧠 Ask your Book
- 📚 Q.A Database
- 🪄 Learn with AR
- 📄 Quiz Generation"""
    )

    st.image("static/logo.png")

st.header(" **🏔️ Welcome to :red[Learn]:blue[Peak]!**", anchor=False)
st.subheader("Engage your learning process with a creative AI Toolkit")
st.markdown(
    """1. Have you ever asked ChatGPT a question from your book but didn't get the answer according to your curriculum?
2. Imagine having a database containing all the question banks from your books that you can search instantly.
3. Would you like to visualize a diagram or scientific model you are studying?
4. Would you like to test your knowledge by generating quizzes from YouTube videos, documents, websites or even from your books to prepare for exams?
"""
)
st.write("**If you want any of these solutions, _LearnPeak_ is your place.**")
"---"

st.subheader("✨ Explore our Features")

# Ask your Book & Q.A Database
with st.container(border=True):
    if st.session_state.get("user_device_type", "mobile") == "pc":
        col1, col2, col3 = st.columns([1, 0.1, 1])

        with col1:
            st.markdown("#### 🧠 Ask your Book")
            st.write("Get instant answers from your curriculum with the power of AI!")

        with col2:
            st.html(
                """
                <div class="divider-vertical-line"></div>
                <style>
                    .divider-vertical-line {
                        border-left: 1px solid rgba(49, 51, 63, 0.2);
                        height: 110px;
                        margin: auto;
                    }
                </style>
                """
            )

        with col3:
            st.markdown("#### 📚 Q.A Database")
            st.write("Instantly find answers to any question in your books!")

        " "
        if st.button("**Ask your Book**", use_container_width=True):
            page = st.Page("pages/ask-book.py", title="Ask your book", icon="🧠")
            st.switch_page(page)

    else:
        st.markdown("#### 🧠 Ask your Book")
        st.write("Get instant answers from your curriculum with the power of AI!")

        st.markdown("#### 📚 Q.A Database")
        st.write("Instantly find answers to any question in your books!")

        " "
        if st.button("**Ask your Book**", use_container_width=True):
            st.switch_page("pages/ask-book.py")

" "
col1, col2 = st.columns(2)
# Learn with AR
with col1.container(border=True):
    st.markdown("#### 🪄 Learn with AR")
    st.write("Visualize your topics with interactive 3D models and AR technology!")
    if st.button("**Generate AR Model**", use_container_width=True):
        st.switch_page("pages/ar.py")

# Quiz Generation
with col2.container(border=True):
    st.markdown("#### 📄 Quiz Generation")
    st.write("Generate quizzes from multiple sources or from your books!")
    if st.button("**Generate Quiz**", use_container_width=True):
        st.switch_page("pages/quizzes.py")

" "
col1, col2 = st.columns(2)
# Record & Recall (Coming Soon)
with col1.container(border=True):
    st.markdown("#### 🎧 Record & Recall")
    st.write(
        "Record your answers for long essay questions instead of leaving them unanswered!"
    )
    st.caption("Coming Soon!")
    st.button(
        "**Record your Answers**",
        help="Coming Soon!",
        disabled=True,
        use_container_width=True,
    )

with col2.container(border=True):
    st.markdown("#### ✒️ Mark Answers")
    st.write("Automatically mark your answers compared to the model answer.")
    st.caption("Coming Soon!")
    st.button(
        "**Mark Answers**",
        help="Coming Soon!",
        disabled=True,
        use_container_width=True,
    )

"---"
st.markdown("#### :red[Learn] :blue[Peak]", text_alignment="center")
st.markdown(
    "**AI tools designed to transform how students interact with their curriculum.**",
    text_alignment="center",
)
