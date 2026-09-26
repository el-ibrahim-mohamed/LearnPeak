import streamlit as st

# Set page config
st.set_page_config(
    page_title="Study Strategies - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

# Hero Header
st.title("🎓 Learn: Core Study Strategies")
st.caption("Master smart study habits to learn faster, remember more, and save time.")

st.divider()

# Section 1: The Basics of Studying
st.header("⚡ The Basics of Studying")
st.write("Before diving into complex techniques, lock in these fundamental habits.")

# Use columns for layout
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 💤 Rest and Focus", anchors=False)

    st.warning(
        "Sleep is when your brain saves what you learned. Studying when you're super tired means you'll forget almost everything.",
        icon="😴",
        title="Never Study Exhausted",
    )

    st.info(
        "Sit up straight at a desk or table. Avoid studying lying down in your bed—your brain thinks it's time to sleep!",
        icon="🏋️",
        title="Sit Up Straight",
    )

with col2:
    st.markdown("### 🧭 Environment & Setup", anchors=False)

    st.error(
        "Put your phone in another room or give it to a parent while you study. Notifications kill your focus.",
        icon="📵",
        title="Zero Phone Distractions",
    )

    st.success(
        "Saying your notes out loud keeps your brain awake and stops your mind from wandering away.",
        icon="🗣️",
        title="Read Out Loud",
    )

"---"

# Strategy 1: Spaced Repetition
st.header("⏳ Strategy 1: Spaced Repetition")
st.write(
    "- Reviewing information at increasing intervals over days or weeks to lock it into long-term memory."
)

# Embedded Video
st.video("https://www.youtube.com/watch?v=cVf38y07cfk")

st.markdown("### 💡 How It Works", anchors=False)

st.error(
    "Have you ever memorized a lesson so well, but completely forgot everything a few days later? \n"
    "Cramming only puts information into your temporary memory, so your brain throws it away quickly.",
    icon="⚠️",
    title="Why Cramming Fails",
)

st.info(
    "Our brains naturally forget things over time. But every time you review a topic just as you're starting to forget it, your brain makes that memory stronger and harder to lose!",
    icon="🧠",
    title="The Forgetting Curve",
)

st.markdown("### 🛠️ How To Do It", anchors=False)

st.success(
    "After finishing a lesson, don't just close the book. Review it again 1 day later, then 3 days later, and then 1 week later. \n"
    "Tougher subjects need more frequent reviews, while easier ones need fewer.",
    icon="📅",
    title="The Review Schedule",
)

"---"
# Strategy 2: Active Recall
st.header("🧠 Strategy 2: Active Recall")
st.write(
    "- Forcing your brain to dig up answers from memory instead of just rereading pages."
)

# Embedded Video
st.video("https://www.youtube.com/watch?v=qv2RsTSoyHI")

st.markdown("### 💡 How It Works", anchors=False)

st.error(
    "Rereading and highlighting your notes over and over makes you *feel* like you know it, but it tricks your brain. When test day comes, the information won't pop up.",
    icon="⚠️",
    title="The Rereading Trap",
)

st.info(
    "Real learning happens when you make your brain work hard to pull up answers from scratch. That mental struggle is what builds permanent memory.",
    icon="⚡",
    title="The Power of Testing Yourself",
)

st.markdown("### 🛠️ How To Do It", anchors=False)

# 2-Column Grid for the 4 Actionable Methods
col1, col2 = st.columns(2, border=True)

with col1:
    st.subheader("🗂️ Flashcards", anchor=False)
    st.write(
        "Look at a question prompt and say the answer out loud *before* you flip the card over."
    )
    
with col2:
    st.subheader("❓ Make Your Own Quiz", anchor=False)
    st.write(
        "Turn your lesson headers into custom questions, wait a day, and try answering them."
    )

col1, col2 = st.columns(2, border=True)

with col1:
    st.subheader("📄 The Blank Page", anchor=False)
    st.write(
        "Close your book, grab a clean sheet of paper, and write down everything you remember about the lesson."
    )

with col2:
    st.subheader("🗣️ Teach Someone Else", anchor=False)
    st.write(
        "Try explaining the core idea out loud in your own simple words, as if teaching a younger sibling."
    )

"---"