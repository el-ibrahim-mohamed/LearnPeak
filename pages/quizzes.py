import streamlit as st
from firebase_admin.db import Reference
import time
from datetime import datetime
from services.quizzes.service import QuizzesService, QuizzesHistory
from config import GRADES, SUBJECTS, UNIT_OPTIONS, LESSON_OPTIONS
from services.rag.embedding_service import EmbeddingService
from services.rag.qdrant_service import QdrantService
from services.rag.rag_service import RagService

# Set page config
st.set_page_config(
    page_title="Quiz Generation - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

# Initializing DB Refrences
root_ref: Reference = st.session_state["root_ref"]
user = st.session_state.get("user", {})
users_ref = root_ref.child("users")


@st.cache_resource
def get_quiz_services():
    return (
        QuizzesService(st.session_state["client"]),
        QuizzesHistory(st.session_state["root_ref"]),
    )


quizzes_service, quizzes_history = get_quiz_services()

st.session_state["quizzes_service"] = quizzes_service


@st.cache_resource
def init_rag_service():
    embedding_service = EmbeddingService()

    qdrant_service = QdrantService(
        url=st.secrets["qdrant"]["URL"],
        api_key=st.secrets["qdrant"]["API_KEY"],
        vector_size=embedding_service.vector_size,
        collection_name="learnpeak_knowledge",
    )

    qdrant_service.ensure_collection_exists()

    return RagService(
        qdrant_service=qdrant_service,
        embedding_service=embedding_service,
        gemini_client=st.session_state["client"],
    )


rag_service = init_rag_service()


def get_key_by_value(d: dict, value):
    return next((k for k, v in d.items() if v == value), None)


def display_quiz(quiz_questions: dict):
    answers = []
    for i, question in enumerate(quiz_questions.values()):
        st.write(f"**Q{i+1}: {question["question"]}**")

        if question["type"] == "mcq":
            user_answer = st.radio(
                "Choices:",
                question["choices"],
                key=f"question{i}",
                index=None,
                label_visibility="collapsed",
            )
            answers.append(user_answer)

        if question["type"] == "true_or_false":
            user_answer = st.radio(
                "Choices:",
                ["True", "False"],
                key=f"question{i}",
                index=None,
                label_visibility="collapsed",
            )
            answers.append(user_answer)

        if question["type"] == "fill_in_the_blank":
            user_answer = st.text_input(
                "Choices:",
                key=f"question{i}",
                placeholder="Your Answer",
                label_visibility="collapsed",
            )
            answers.append(user_answer)

        "---"

    return answers


def display_graded_quiz(quiz_questions: dict, quiz_grading: dict):
    for i, id in enumerate(quiz_questions):
        question_result = quiz_grading[id]

        grade_icon = "✅" if question_result == True else "❌"
        st.write(f"**{grade_icon} Q{i+1}: {quiz_questions[id]["question"]}**")

        if quiz_questions[id]["type"] == "mcq":
            st.radio(
                "Choices:",
                quiz_questions[id]["choices"],
                key=f"question{i}",
                index=None,
                label_visibility="collapsed",
                disabled=True,
            )

        if quiz_questions[id]["type"] == "true_or_false":
            st.radio(
                "Choices:",
                ["True", "False"],
                key=f"question{i}",
                index=None,
                label_visibility="collapsed",
                disabled=True,
            )

        if quiz_questions[id]["type"] == "fill_in_the_blank":
            st.text_input(
                "Choices:",
                key=f"question{i}",
                placeholder="Your Answer",
                label_visibility="collapsed",
                disabled=True,
            )

        if question_result != True:
            st.info(f"**AI Overview**: {question_result}")

        "---"


def open_quiz(quiz: dict):
    """Load a quiz from history to display it"""
    st.session_state["quiz_info"] = quiz["quiz_info"]
    st.session_state["quiz_questions"] = quiz["quiz_questions"]
    st.session_state["quiz_id"] = quiz["id"]
    st.session_state["quiz_started"] = True
    st.session_state["quiz_submitted"] = False
    st.session_state["scroll_to_top"] = True
    st.rerun()


# Scrolling Logic
if st.session_state.get("scroll_to_top"):
    js = """
    <script>
        window.parent.document.querySelector('section.stMain').scrollTo({top: 0});
    </script>
    """
    # , behavior: 'smooth'
    st.html(js, unsafe_allow_javascript=True)
    st.session_state["scroll_to_top"] = False


# Creating the Quiz
if not st.session_state.get("quiz_started"):
    st.title("📝 Quiz Generation", anchor=False)
    "---"

    # Quiz Title
    title = st.text_input("🏷️ **Title :red[*]**")
    " "

    # Description
    description = st.text_area(
        "📄 **Description**",
        height=120,
        placeholder="e.g. Quiz on unit 2 lesson 1.",
    )
    "---"

    # Sources
    st.write("📚 **Textbook Sources**")

    col1, col2 = st.columns(2)

    with col1:
        grade_options = list(GRADES.keys())
        grade_index = None

        if user:
            grade_index = grade_options.index(get_key_by_value(GRADES, user["grade"]))

        selected_grade = st.selectbox(
            "Grade", grade_options, index=grade_index, placeholder="Choose your grade"
        )

    with col2:
        subject_options = list(SUBJECTS.keys())
        subject_index = 0

        selected_subject = st.selectbox(
            "Subject",
            subject_options,
            index=subject_index,
        )

    col1, col2 = st.columns(2)

    with col1:
        selected_units = st.multiselect(
            "Units",
            UNIT_OPTIONS,
            placeholder="All units",
        )

    with col2:
        selected_lessons = st.multiselect(
            "Lessons",
            LESSON_OPTIONS,
            placeholder="All lessons",
        )

    st.caption(
        "Select a subject to use your curriculum textbook as a quiz source. "
        "Leave units or lessons empty to include all of them."
    )

    "---"

    # External Sources
    with st.expander("🔗 **External Sources**"):
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ("📝 Text", "🎧 Audio", "🎥 Video", "📕 Files", "🌐 Website")
        )

        with tab1:
            text = st.text_area("**Text**", height=200)

        with tab2:
            audios = st.file_uploader(
                "**Audio**",
                accept_multiple_files=True,
                type=(
                    "aac",
                    "flac",
                    "mp3",
                    "m4a",
                    "mpeg",
                    "mpga",
                    "mp4",
                    "ogg",
                    "pcm",
                    "wav",
                    "webm",
                ),
            )

        with tab3:
            videos = st.file_uploader(
                "**Videos**",
                accept_multiple_files=True,
                type=(
                    "flv",
                    "mov",
                    "mpeg",
                    "mpegs",
                    "mpg",
                    "mp4",
                    "webm",
                    "wmv",
                    "3gpp",
                    "avi",
                ),
            )
            "---"

            st.write("**YouTube Videos**")
            col1, _, _ = st.columns(3)
            number = col1.number_input("Number", min_value=0, value=1)
            " "

            youtube_videos_urls = []
            for i in range(number):
                i += 1
                youtube_video = st.text_input(
                    f"YouTube Video {i}",
                    key=f"youtube_video_{i}",
                    placeholder="Video URL",
                )
                if youtube_video:
                    youtube_videos_urls.append(youtube_video)

        with tab4:
            files = st.file_uploader(
                "**Files**",
                accept_multiple_files=True,
                type=("pdf", "docx", "pptx", "xlsx", "txt", "html", "md"),
            )

        with tab5:
            st.write("**Websites**")
            col1, _, _ = st.columns(3)
            number = col1.number_input("Number", min_value=0, value=1, max_value=20)
            " "

            web_urls = []
            for i in range(number):
                i += 1
                web_url = st.text_input(
                    f"Website {i}", key=f"web_url_{i}", placeholder="Website URL"
                )
                if web_url:
                    web_urls.append(web_url)

        " "
        st.info("You can provide more than one source.", icon="ℹ️")
    " "

    # Number of questions
    number_of_questions = st.number_input(
        "**Number of Questions :red[*]**", min_value=1, value=5, max_value=100
    )
    " "

    # Difficulty
    st.write("**Difficulty :red[*]**")
    difficulty = st.select_slider(
        "**Difficulty**",
        options=("Auto", "Very Easy", "Easy", "Medium", "Hard", "Very Hard"),
        label_visibility="collapsed",
    )

    # Custom instructions
    custom_inst = st.text_area(
        "**Custom instructions**",
        height=120,
        placeholder="e.g. Limit the quiz to this part",
    )

    " "
    if st.button("Generate Quiz", type="primary", icon="✨", use_container_width=True):
        valid_inputs = True

        if not title:
            st.error("Missing a required field: Title")
            valid_inputs = False

        if valid_inputs:
            book_text = ""
            selected_grade_value = GRADES[selected_grade] if selected_grade else None
            selected_subject_value = (
                SUBJECTS[selected_subject] if selected_subject else None
            )
            audios = [
                {"bytes": audio.getvalue(), "name": audio.name} for audio in audios
            ]
            videos = [
                {"bytes": video.getvalue(), "name": video.name} for video in videos
            ]
            files = [{"bytes": file.getvalue(), "name": file.name} for file in files]

            if selected_grade_value and selected_subject_value:
                with st.spinner("Preparing your sources...", show_time=True):
                    country = user["country"].lower() if user else "egypt"
                    education = user["education"] if user else "national"
                    book_text: str = rag_service.get_sources_from_filters(
                        country,
                        education,
                        selected_grade_value,
                        selected_subject_value,
                        selected_units,
                        selected_lessons,
                    )

            found_sources = True
            if selected_grade_value and selected_subject_value and not book_text:
                found_sources = False
                st.warning(
                    "No textbook content was found for the selected filters. You can "
                    "still generate the quiz using external sources or without sources."
                )

            if found_sources:
                with st.spinner("Generating your Quiz...", show_time=True):
                    quiz_info = {
                        "title": title,
                        "number_of_questions": number_of_questions,
                        "difficulty": difficulty,
                        "description": description,
                    }

                    quiz_questions = st.session_state.quizzes_service.generate_quiz(
                        **quiz_info,
                        book_text=book_text,
                        text=text,
                        audios=audios,
                        videos=videos,
                        youtube_videos_urls=youtube_videos_urls,
                        files=files,
                        web_urls=web_urls,
                        custom_instructions=custom_inst,
                    )

                st.session_state["quiz_info"] = quiz_info
                st.session_state["quiz_questions"] = quiz_questions
                st.session_state["quiz_started"] = True
                st.session_state["scroll_to_top"] = True
                st.rerun()

    "---"
    with st.expander("📂 History"):
        quizzes = []

        # Getting quizzes data with their IDs
        if st.session_state.get("user"):
            quizzes = quizzes_history.get_saved_quizzes(st.session_state["user"]["uid"])

        if quizzes:
            streamlit_colors = [
                "red",
                "blue",
                "orange",
                "yellow",
                "green",
                "violet",
                "gray",
            ]

            for i, quiz in enumerate(quizzes):
                chosen_color = streamlit_colors[i % len(streamlit_colors)]

                quiz_title = quiz["quiz_info"]["title"]
                col1, col2, col3 = st.columns([4, 1, 1], vertical_alignment="center")

                with col1:
                    st.subheader(
                        f":{chosen_color}[{quiz_title}]",
                        anchor=False,
                    )

                    timestamp = quiz["created_at"]
                    dt = datetime.fromtimestamp(timestamp)
                    date_time = dt.strftime(
                        "%B %d, %Y at %I:%M %p"
                    )  # Example: "January 24, 2026 at 03:30 PM"
                    st.caption(f"Created: {date_time}")

                with col2:
                    if st.button(
                        "Open",
                        key=f"open_{quiz['id']}",
                        icon="📖",
                        use_container_width=True,
                    ):
                        open_quiz(quiz)

                with col3:
                    if st.button(
                        "Delete",
                        key=f"delete_{quiz['id']}",
                        icon="🗑️",
                        use_container_width=True,
                    ):
                        quizzes_history.delete_quiz(
                            st.session_state["user"]["uid"],
                            quiz["id"],
                        )

                        st.success(f"Deleted '{quiz_title}'")
                        st.rerun()

                if i != len(quizzes) - 1:
                    "---"

        else:
            st.info("No quizzes found. Create your first one!")

# Generated the Quiz
else:
    # Solving the Quiz
    if not st.session_state.get("quiz_submitted"):
        st.title(f"📃 Quiz - :blue[{st.session_state["quiz_info"]["title"]}]")
        "---"

        answers = display_quiz(st.session_state["quiz_questions"])

        if st.button("End Quiz", icon="❌", use_container_width=True):

            def end_quiz():
                st.session_state["quiz_started"] = False
                st.session_state["scroll_to_top"] = True
                st.rerun()

            if any(answers):

                @st.dialog("End Quiz")
                def end_quiz_dialog():
                    st.write("**Are you sure you want to end this quiz?**")
                    st.info("Your answers will not be saved!")

                    col1, col2 = st.columns(2)
                    if col1.button("No", type="primary", use_container_width=True):
                        st.rerun()

                    if col2.button("Yes", use_container_width=True):
                        end_quiz()

                end_quiz_dialog()

            else:
                end_quiz()

        if st.button("Submit", type="primary", icon="🚀", use_container_width=True):

            if not all(answers):

                @st.dialog("Uncompleted Answers")
                def missing_answers_dialog():
                    st.write("**Are you sure you want to submit the quiz?**")
                    st.info("Some answer fields are empty")

                    col1, col2 = st.columns(2)
                    if col1.button("No", type="primary", use_container_width=True):
                        st.rerun()

                    if col2.button("Yes", use_container_width=True):
                        quiz_grading = st.session_state.quizzes_service.grade_quiz(
                            st.session_state["quiz_questions"], answers
                        )
                        st.session_state["quiz_grading"] = quiz_grading
                        st.session_state["quiz_submitted"] = True
                        st.session_state["scroll_to_top"] = True
                        st.rerun()

                missing_answers_dialog()

            else:
                with st.spinner("Grading your Quiz..."):
                    quiz_grading = st.session_state.quizzes_service.grade_quiz(
                        st.session_state["quiz_questions"], answers
                    )

                st.session_state["quiz_grading"] = quiz_grading
                st.session_state["quiz_submitted"] = True
                st.session_state["scroll_to_top"] = True
                st.rerun()

        # Auto-save quiz if not already saved
        if (
            not st.session_state.get("quiz_id")
            and st.session_state["quiz_info"]
            and st.session_state["quiz_questions"]
        ):
            if not st.session_state.get("user") and not st.session_state.get(
                "quiz_sign_in_offer", False
            ):

                @st.dialog("Get Started")
                def sign_in_offer():
                    st.info("Sign In to start saving your history!")

                    if st.button(
                        "Sign In", type="primary", icon="🔐", use_container_width=True
                    ):
                        st.session_state["page_before_auth"] = "quizzes"
                        st.switch_page("pages/signin.py")

                    if st.button(
                        "Create Account",
                        type="primary",
                        icon="👤",
                        use_container_width=True,
                    ):
                        st.session_state["page_before_auth"] = "quizzes"
                        st.switch_page("pages/signup.py")

                sign_in_offer()
                st.session_state["quiz_sign_in_offer"] = True

            elif st.session_state.get("user"):
                st.session_state["quiz_id"] = quizzes_history.save_quiz(
                    st.session_state["user"]["uid"],
                    st.session_state["quiz_info"],
                    st.session_state["quiz_questions"],
                )

    # Submitted the Quiz - Display Grading
    else:
        st.title(f"💯 Quiz Grading - {st.session_state["quiz_info"]["title"]}")
        "---"

        display_graded_quiz(
            st.session_state["quiz_questions"], st.session_state["quiz_grading"]
        )

        if (
            st.session_state.get("user")
            and st.session_state.get("quiz_id")
            and not st.session_state.get("grading_saved")
        ):
            grading_id = quizzes_history.save_quiz_grading(
                st.session_state["user"]["uid"],
                st.session_state["quiz_id"],
                st.session_state["quiz_grading"],
            )

            st.session_state["grading_id"] = grading_id
            st.session_state["grading_saved"] = True

        col1, col2 = st.columns(2)

        if col1.button(
            "Generate A New Quiz", type="primary", icon="📝", use_container_width=True
        ):
            st.session_state["quiz_started"] = False
            st.session_state["quiz_submitted"] = False

            st.session_state["quiz_id"] = None
            st.session_state["quiz_info"] = None
            st.session_state["quiz_questions"] = None
            st.session_state["quiz_grading"] = None

            st.session_state["grading_id"] = None
            st.session_state["grading_saved"] = False

            st.session_state["scroll_to_top"] = True
            st.rerun()

        if col2.button("Retake The Quiz", icon="🔃", use_container_width=True):
            st.session_state["quiz_submitted"] = False
            st.session_state["quiz_grading"] = None

            st.session_state["grading_id"] = None
            st.session_state["grading_saved"] = False

            st.session_state["scroll_to_top"] = True
            st.rerun()
