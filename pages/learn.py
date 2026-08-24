import streamlit as st

# Set page config
st.set_page_config(
    page_title="Learn Study Strategies - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

# Hero Header
st.title("🎓 Learn: Core Study Strategies")
st.caption("Master evidence-based techniques to learn faster and retain more.")

st.divider()

# Section 1: The Basics of Studying
st.header("⚡ The Basics of Studying")
st.write("Before diving into complex techniques, lock in these **fundamental** habits.")

# Use columns for layout
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 💤 Rest and Alertness", anchors=False)

    # warning/orange tone for energy/sleep alerts
    st.warning(
        "Sleep consolidates memory. Studying while sleepy yields near-zero retention.",
        icon="😴",
        title="Never Study Exhausted",
    )

    # info/blue tone for standard biological positioning
    st.info(
        "Sit up at a desk. Avoid studying in your bed at all costs.",
        icon="🏋️",
        title="Active Physiology",
    )

    # Use regular markdown with a colored header/emoji for the third point
    st.success(
        "Verbalizing forces your brain to stay engaged and stops mind-wandering.",
        icon="🗣️",
        title="Read Out Loud",
    )

with col2:
    st.markdown("### 🧭 Environment & Focus", anchors=False)

    # error/red tone for absolute restrictions like distractions
    st.error(
        "Keep your phone in another room or hand it to a parent/friend.",
        icon="📵",
        title="Zero Phone Distraction",
    )

    st.info(
        "Use the same clean desk area to prime your brain for focus mode.",
        icon="🖥️",
        title="Dedicated Space",
    )

    st.success(
        "Keep fresh water nearby and ensure bright, clear lighting.",
        icon="💡",
        title="Hydration & Light",
    )

"---"

# Strategy 1: Spaced Repetition
st.header("⏳ Strategy 1: Spaced Repetition")
st.write(
    "- Distributing your study sessions over time to build permanent long-term memory."
)

# Embedded Video
st.video("https://www.youtube.com/watch?v=cVf38y07cfk")

st.markdown("### 💡 How It Works", anchors=False)

# Warning/Error tone for why cramming fails
st.error(
    "Have you ever studied really hard for a lesson, but then totally forgot it a few days later?  \n"
    "Cramming puts information in your **short-term** memory, and your brain quickly forgets it because it wasn't practiced enough.",
    icon="⚠️",
    title="Why Cramming Fails",
)

# Info/Blue tone for the science mechanism
st.info(
    "Your brain naturally forgets information along the **Ebbinghaus Forgetting Curve**.  \n"
    "When you review something just before you're about to forget it, your brain builds a stronger memory, making it easier to remember later.",
    icon="🧠",
    title="The Forgetting Curve",
)

st.markdown("### 🛠️ How To Do It", anchors=False)

# Success/Green tone for practice & intervals
st.success(
    "Once you finish studying a lesson, don't just leave it—schedule **review sessions** at expanding intervals (e.g., 1 day later, 3 days later, 7 days later).  \n"
    "Change these times based on how hard the lesson is: tougher topics need shorter gaps, while easier ones can have longer breaks.",
    icon="📅",
    title="Strategic Review Intervals",
)

"---"
# Strategy 2: Active Recall
st.header("🧠 Strategy 2: Active Recall")
st.write(
    "- Forcing your brain to retrieve information from memory instead of passively reviewing it."
)

# Embedded Video
st.video("https://www.youtube.com/watch?v=qv2RsTSoyHI")

st.markdown("### 💡 How It Works", anchors=False)

# Re-engineered for impact and brevity
st.error(
    "Passive review (rereading and highlighting) only builds familiarity, **not memory**. "
    "It creates an illusion where information looks recognizable, but remains impossible to retrieve during a test.",
    icon="⚠️",
    title="The Passive Review Trap",
)

st.info(
    "True learning happens through retrieval practice. "
    "Forcing your brain to struggle and pull information from scratch creates stronger, permanent **neural pathways**.",
    icon="⚡",
    title="The Retrieval Mechanism",
)

st.markdown("### 🛠️ How To Do It", anchors=False)

# 2-Column Grid for the 4 Actionable Methods
col1, col2 = st.columns(2, border=True)

with col1:
    st.subheader("🗂️ Flashcards", anchor=False)
    st.write(
        "Look at a prompt and explicitly say or write the answer *before* flipping the card."
    )
    
with col2:
    st.subheader("❓ Self-Testing", anchor=False)
    st.write(
        "Turn your lecture notes and headers into custom practice questions, then test yourself later."
    )

col1, col2 = st.columns(2, border=True)

with col1:
    st.subheader("📄 The Blank Page", anchor=False)
    st.write(
        "Close your book, open a blank sheet, and write down absolutely everything you can remember."
    )

with col2:
    st.subheader("🗣️ Teaching Others", anchor=False)
    st.write(
        "Explain the core concept out loud in your own simple words, as if teaching it to a complete beginner."
    )

"---"
