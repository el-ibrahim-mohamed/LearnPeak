import streamlit as st
import base64

# Set page config
st.set_page_config(
    page_title="About LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("⛰️ About :red[Learn]:blue[Peak]", anchor=False, text_alignment="center")
" "

st.markdown("""
    ### LearnPeak — AI Tools Built for Your Curriculum

    **LearnPeak** is an AI-powered educational platform designed to make
    studying smarter, more interactive, and more personalized.

    Instead of giving students generic AI tools, LearnPeak focuses on
    **their actual school curriculum and textbooks**.
    """)

"---"


# ---------------------------------------------------------
# WHY LEARNPEAK
# ---------------------------------------------------------

st.header("🎯 Why LearnPeak?", anchor=False)

st.markdown("""
    Studying is not just about spending more time with a book.
    It is about using the right tools and strategies to understand,
    remember, and apply what you learn.

    LearnPeak brings AI-powered learning tools together in one place,
    while keeping the student's **curriculum at the center of the experience**.
    """)

"---"


# ---------------------------------------------------------
# FEATURES
# ---------------------------------------------------------

st.header("🚀 What You Can Do", anchor=False)

col1, col2 = st.columns(2)
col1.success(
    "Ask questions about your textbooks and get answers grounded in the content you're studying.",
    icon="📚",
    title="Ask Your Book",
)
col2.info(
    "Explore interactive 3D models and AR learning experiences for a more visual way to understand concepts.",
    icon="🥽",
    title="Learn with AR",
)

col1, col2 = st.columns(2)
col1.info(
    "Generate quizzes from your textbook, specific units or lessons, and additional external sources.",
    icon="📝",
    title="Quiz Generation",
)
col2.success(
    "Learn and apply science-backed learning strategies to learn and retain information more effectively.",
    icon="🧠",
    title="Study Strategies",
)

"---"


# ---------------------------------------------------------
# OUR APPROACH
# ---------------------------------------------------------

st.header("🧠 Our Approach", anchor=False)

st.markdown("""
    LearnPeak is built around a simple idea:

    > **AI should adapt to the way students learn — not the other way around.**

    Our goal is to combine AI with effective learning strategies to help
    students understand concepts deeply, practice what they know, and
    retain information for longer.

    The platform is continuously evolving as we add new learning tools,
    improve existing ones, and expand curriculum coverage.
    """)

"---"


# ---------------------------------------------------------
# FOUNDER
# ---------------------------------------------------------

# Founder image b64
image_path = "static/founder.jpeg"

with open(image_path, "rb") as image_file:
    image_base64 = base64.b64encode(image_file.read()).decode()

# Founder information
name = "Ibrahim Mohamed"
role = "Founder & Developer"

description = """
I am the founder and developer of LearnPeak, building AI-powered
educational tools designed around the student's actual curriculum.
My goal is to make learning more personalized, interactive, and effective.
"""

linkedin_url = "https://www.linkedin.com/in/ibrahim-mo-dev/"
github_url = "https://github.com/el-ibrahim-mohamed/"

# Founder UI
st.html(
    f"""
    <style>
        .founder-container {{
            display: flex;
            align-items: center;
            gap: 64px;
            width: 100%;
            margin-top: 10px;
        }}

        .founder-image {{
            width: 290px;
            height: 290px;
            min-width: 290px;
            border-radius: 50%;
            object-fit: cover;
            border: 7px solid #7A2945;
            box-sizing: border-box;
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.12);
        }}

        .founder-content {{
            flex: 1;
            min-width: 0;
        }}

        .founder-label {{
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-bottom: 8px;
            opacity: 0.65;
        }}

        .founder-name {{
            font-size: 38px;
            font-weight: 700;
            line-height: 1.15;
            margin: 0;
            color: #123456;
        }}

        .founder-role {{
            font-size: 22px;
            font-weight: 500;
            margin-top: 7px;
            margin-bottom: 25px;
            color: #B96F7F;
        }}

        .founder-description {{
            font-size: 19px;
            line-height: 1.65;
            margin: 0 0 24px 0;
            color: inherit;
        }}

        .founder-links {{
            display: flex;
            gap: 20px;
            align-items: center;
        }}

        .founder-link {{
            text-decoration: none !important;
            font-size: 16px;
            font-weight: 600;
            transition: opacity 0.2s ease;
        }}

        .founder-link:hover {{
            opacity: 0.65;
        }}

        @media (max-width: 700px) {{
            .founder-container {{
                flex-direction: column;
                gap: 28px;
                text-align: center;
            }}

            .founder-image {{
                width: 230px;
                height: 230px;
                min-width: 230px;
            }}

            .founder-name {{
                font-size: 30px;
            }}

            .founder-role {{
                font-size: 19px;
            }}

            .founder-description {{
                font-size: 17px;
            }}

            .founder-links {{
                justify-content: center;
            }}
        }}
    </style>

    <div class="founder-container">

        <img
            class="founder-image"
            src="data:image/jpeg;base64,{image_base64}"
        >

        <div class="founder-content">

            <div class="founder-label">
                Built by
            </div>

            <h2 class="founder-name">
                {name}
            </h2>

            <div class="founder-role">
                {role}
            </div>

            <p class="founder-description">
                {description}
            </p>

            <div class="founder-links">
                <a
                    class="founder-link"
                    href="{linkedin_url}"
                    target="_blank"
                    style="color: #0A66C2;"
                >
                    ↗ LinkedIn
                </a>

                <a
                    class="founder-link"
                    href="{github_url}"
                    target="_blank"
                >
                    ↗ GitHub
                </a>
            </div>

        </div>

    </div>
    """,
)

"---"

# ---------------------------------------------------------
# VISION
# ---------------------------------------------------------

st.header("🌟 Our Vision", anchor=False)

st.markdown("""
    We want to make high-quality, personalized learning tools accessible
    to students — tools that understand **what they are studying**, not
    just what they are asking.

    **Learn smarter. Learn your way. Reach your peak.**
    """)

"---"

# ---------------------------------------------------------
# LINKS & RESOURCES
# ---------------------------------------------------------

st.header("🔗 Links & Resources", anchor=False)
" "

st.markdown(
    """
    - 🌐 **[LearnPeak Application](https://learnpeak.streamlit.app/)**  
      Access and use the LearnPeak platform.

    - 💻 **[LearnPeak GitHub Repository](https://github.com/el-ibrahim-mohamed/LearnPeak)**  
      View the source code and project information.

    - 📧 **[Official Email](mailto:learnpeak.eg@gmail.com)**  
      Contact the LearnPeak team.
    """
)

"---"

st.markdown(
    """
    <div style="text-align: center;">
        <b>Built with 💙 for students by a student.</b>
    </div>
    """,
    unsafe_allow_html=True,
)
