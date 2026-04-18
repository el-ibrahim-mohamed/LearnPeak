import streamlit as st

# Sidebar
with st.sidebar:
    if st.session_state.get("user"):
        full_name: str = st.session_state["user"]["full_name"]
        st.title(f"👋 Welcome back :blue[{full_name.split()[0]}]!")
    else:
        st.title("👋 Welcome to :red[Learn]:blue[Peak]!")

    " "
    st.write("🔎 AI-powered tools to boost your learning:")
    st.write(
        """- 🧠 Ask your Book  
- 📚 Q.A Database  
- 🪄 Learn with AR  
- 📄 Quiz Generation"""
    )

    st.image("static/logo.png")

# Hero Section
st.markdown(
    """
    <h1 style='text-align: center;'>
        🏔️ <span style='color:#ff4b4b;'>Learn</span><span style='color:#1f77b4;'>Peak</span>
    </h1>
    <h3 style='text-align: center; font-weight: normal;'>
    Study smarter with AI that understands YOUR curriculum
    </h3>
    """,
    unsafe_allow_html=True
)

" "

col1, col2, col3 = st.columns([1,2,1])
with col2:
    if st.button("🚀 Start with Ask Your Book", use_container_width=True):
        st.switch_page("pages/ask-book.py")

" "

# Value Points
st.markdown(
    """
    <div style='text-align: center; font-size: 16px;'>
    ✔ Answers based on your curriculum<br>
    ✔ Instant question bank search<br>
    ✔ Generate quizzes from any source<br>
    ✔ Visualize lessons with AR
    </div>
    """,
    unsafe_allow_html=True
)

"---"

# Features
st.subheader("✨ Explore Features")

# Main Feature (highlighted)
with st.container(border=True):
    st.markdown("### 🧠 Ask Your Book (Core)")
    st.write("Ask anything from your curriculum and get accurate, AI-powered answers instantly.")
    st.write("Search thousands of questions from your textbooks instantly.")
    if st.button("Start Asking", use_container_width=True):
        st.switch_page("pages/ask-book.py")

" "

col1, col2 = st.columns(2)

with col1.container(border=True, horizontal_alignment="center"):
    st.markdown("#### 🪄 Learn with AR")
    st.write("Visualize complex topics using interactive 3D models.")
    if st.button("Open AR", use_container_width=True):
        st.switch_page("pages/ar.py")

with col2.container(border=True):
    st.markdown("#### 📄 Quiz Generation")
    st.write("Generate quizzes from videos, documents, websites, or your books.")
    if st.button("Generate Quiz", use_container_width=True):
        st.switch_page("pages/quizzes.py")

" "

col1, col2 = st.columns(2)

with col1.container(border=True):
    st.markdown("#### ✒️ Auto Mark Answers")
    st.write("Get instant feedback by comparing your answers with model answers.")

    st.button("Coming Soon", key="coming_soon_1", disabled=True, use_container_width=True)

with col2.container(border=True):
    st.markdown("#### 🎧 Record & Recall")
    st.write("Answer long questions by recording your voice.")
    st.button("Coming Soon", key="coming_soon_2", disabled=True, use_container_width=True)

" "

# Footer #
"---"
st.markdown("### :red[Learn]:blue[Peak]", text_alignment="center")
st.markdown(
    "AI tools designed to transform how students interact with their curriculum.",
    text_alignment="center",
)