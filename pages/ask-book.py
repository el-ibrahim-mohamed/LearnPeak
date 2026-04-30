import streamlit as st
import streamlit.components.v1 as components
from streamlit_shortcuts import shortcut_button
from streamlit_theme import st_theme
from typing import Literal
import re
import uuid
from rag.chat_service import ChatService


# Defining Functions
def clean_string(input_str: str):
    return (
        "".join(char for char in input_str if char.isalnum() or char.isspace())
        .strip()
        .replace("  ", " ")
        .replace(" ", "_")
    )


def get_key_by_value(d: dict, value):
    return next((k for k, v in d.items() if v == value), None)


# Initialize session states
if "msgs_visible_counts" not in st.session_state:
    st.session_state["msgs_visible_counts"] = {}

# Loading the RAG system
st.sidebar.title("🧠 LearnPeak :blue[RAG] System")
with st.spinner("Loading LearnPeak RAG System...", show_time=True):
    with st.spinner("Importing services..."):
        from qdrant_client.models import (
            PayloadSchemaType,
            Filter,
            FieldCondition,
            MatchValue,
        )
        from rag.embedding_service import EmbeddingService
        from rag.qdrant_service import QdrantService
        from rag.rag_service import RagService, AddSource

    # Initialize Services (Cached)
    @st.cache_resource()
    def init_services():
        embedding_service = EmbeddingService()
        qdrant_service = QdrantService(
            url=st.secrets["qdrant"]["URL"],
            api_key=st.secrets["qdrant"]["API_KEY"],
            vector_size=embedding_service.vector_size,
            collection_name="learnpeak_knowledge",
        )

        qdrant_service.ensure_collection_exists()

        for payload_key in [
            "point_type",
            "country",
            "education",
            "book_publisher",
            "id",
            "grade",
            "subject",
            "lesson_id",
            "ex_type",
            "ex_title",
        ]:
            qdrant_service.create_payload_index(
                qdrant_service.collection_name,
                payload_key,
                PayloadSchemaType.KEYWORD,
            )

        for payload_key in ["term", "unit_num", "lesson_num", "page"]:
            qdrant_service.create_payload_index(
                qdrant_service.collection_name,
                payload_key,
                PayloadSchemaType.INTEGER,  # <-- changed
            )

        return (
            RagService(qdrant_service, embedding_service, st.session_state["client"]),
            ChatService(st.session_state.get("root_ref")),
        )

    rag_service, chat_service = init_services()

with st.sidebar:
    " "

    if st.button("Back to menu", icon="🔙", use_container_width=True):
        st.session_state["rag_page"] = "menu"
        st.session_state["messages_data"] = []
        st.session_state["current_chat_id"] = None

    if shortcut_button(
        "New chat",
        "ctrl+k",
        hint=False,
        type="primary",
        icon="📝",
        use_container_width=True,
        help="Ctrl + K",
    ):
        st.session_state["rag_page"] = "chat"
        st.session_state["messages_data"] = []
        st.session_state["current_chat_id"] = None

    st.caption("Your chats")

    # Load and display previous chats
    if st.session_state.get("user"):
        username = st.session_state["user"]["username"]
        chats = chat_service.get_chats(username)

        if chats:
            for chat in chats:
                col1, col2, col3 = st.columns(
                    [0.65, 0.20, 0.15], vertical_alignment="center"
                )

                with col1:
                    chat_title = chat["title"]
                    chat_title = (
                        chat_title if len(chat_title) <= 35 else f"{chat_title[:35]}.."
                    )

                    if st.button(
                        chat_title,
                        key=f"chat_{chat['id']}",
                        use_container_width=True,
                    ):
                        # Load messages from Firebase
                        db_messages = chat_service.get_chat_messages(
                            username, chat["id"]
                        )

                        # Convert DB → UI format
                        formatted_messages = []
                        for m in db_messages:
                            if m["role"] == "user":
                                formatted_messages.append(
                                    {"role": "user", "msg": m.get("content", "")}
                                )
                            else:
                                formatted_messages.append(
                                    {
                                        "id": str(uuid.uuid4()),
                                        "role": "assistant",
                                        "ai_response": m.get("content", ""),
                                        "similar_questions": m.get(
                                            "similar_questions", []
                                        ),
                                        "is_q_error": False,
                                        "is_ai_error": False,
                                    }
                                )

                        # 4. Save to session state
                        st.session_state["rag_page"] = "chat"
                        st.session_state["current_chat_id"] = chat["id"]
                        st.session_state["messages_data"] = formatted_messages

                with col2:
                    with st.popover("", icon="✏️"):
                        with st.form(f"chat_rename_{chat['id']}", border=False):
                            new_chat_title = st.text_input(
                                "New chat name",
                                value=chat["title"],
                                icon="✍️",
                                label_visibility="collapsed",
                            )
                            if st.form_submit_button(
                                "Save", icon="💾", use_container_width=True
                            ):
                                chat_service.update_title(
                                    username,
                                    chat["id"],
                                    new_chat_title,
                                )
                                st.rerun()

                with col3:
                    if st.button(
                        "", key=f"del_{chat['id']}", icon="🗑️", use_container_width=True
                    ):
                        chat_service.delete_chat(username, chat["id"])
                        st.session_state["rag_page"] = "chat"
                        st.session_state["messages_data"] = []
                        st.session_state["current_chat_id"] = None
                        st.rerun()
        else:
            st.info("No chats found. Create your first one!")

subjects = [
    "📖 English",
    "🔢 Math",
    "🔬 Science",
    "📚 Arabic",
    "🌍 Social Studies",
    "🕌 Islamic Religion",
    "🇩🇪 German",
    "💻 ICT",
]
grades = {
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


page = st.session_state.get("rag_page", "menu")

# Menu page
if page == "menu":
    st.title("📚 Choose your subject", anchor=False)
    "---"

    def button_container_html(btn_key):
        st.markdown(
            f"""
            <style>
            .st-key-{btn_key} button {{
                height: auto;
                padding: 20px;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
                text-align: center;
                display: block;
                transition: all 0.3s ease-in-out;
                white-space: pre-wrap;
            }}

            .st-key-{btn_key} button:hover {{
                border-color: #ff4b4b;
                background-color: #f9f9f9;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                transform: translateY(-2px);
            }}
            
            .st-key-{btn_key} button p {{
                margin: 0;
                line-height: 1.5;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.subheader("🌍 All Grades")
    btn_key = "all_grades_btn"
    button_container_html(btn_key)

    if st.button(
        "🔍 Browse All Subjects",
        use_container_width=True,
        key=btn_key,
        help="Search across all grades and subjects",
    ):
        st.session_state["menu_choice"] = "all_grades"
        st.session_state["rag_page"] = "chat"
        st.session_state["messages_data"] = []
        st.session_state["current_chat_id"] = None
        st.rerun()

    if st.session_state.get("user"):
        " "
        user_grade_long = get_key_by_value(grades, st.session_state["user"]["grade"])

        st.subheader(user_grade_long)

        # Display subjects for user's grade
        cols = st.columns(2)
        menu_subjects = ["🔬 Science"]

        for i in range(0, len(menu_subjects), 2):
            col1, col2 = st.columns(2)

            # First item in row
            subject = menu_subjects[i]
            subj_code = clean_string(subject).lower()
            btn_key = f"subject_{subj_code}"

            with col1:
                button_container_html(btn_key)
                if st.button(subject, use_container_width=True, key=btn_key):
                    st.session_state["menu_choice"] = subj_code
                    st.session_state["rag_page"] = "chat"
                    st.session_state["messages_data"] = []
                    st.session_state["current_chat_id"] = None
                    st.rerun()

            # Second item in row (if exists)
            if i + 1 < len(menu_subjects):
                subject = menu_subjects[i + 1]
                subj_code = clean_string(subject).lower()
                btn_key = f"subject_{subj_code}"

                with col2:
                    button_container_html(btn_key)
                    if st.button(subject, use_container_width=True, key=btn_key):
                        st.session_state["menu_choice"] = subj_code
                        st.session_state["rag_page"] = "chat"
                        st.session_state["messages_data"] = []
                        st.session_state["current_chat_id"] = None
                        st.rerun()

        "---"

        def switch_to_add_source():
            st.session_state["rag_page"] = "add_source"

        st.button(
            "Add your own sources (Coming Soon)",
            type="primary",
            on_click=switch_to_add_source(),
            icon="➕",
            disabled=True,
            use_container_width=True,
        )

    else:
        st.info("Sign in to see subjects for your grade in the menu page")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sign In", icon="🔐", use_container_width=True):
                st.switch_page("pages/signin.py")
        with col2:
            if st.button(
                "Create Account",
                type="primary",
                icon="👤",
                use_container_width=True,
            ):
                st.switch_page("pages/signin.py")

# Add source page
if page == "add_source":
    st.title("➕ Add a Source")
    "---"

    st.error("This feature is will be available after adding our curriculum books.")
    st.stop()

    @st.cache_resource()
    def get_add_source_service(_client, _rag_service, grade):
        return AddSource(_client, _rag_service, grade)

    if st.session_state.get("user"):
        grade = st.session_state["user"]["grade"]
        st.session_state["add_source_service"] = get_add_source_service(
            st.session_state["client"], rag_service, grade
        )

    else:
        add_source_service = None
        st.info(
            "🔏 You need to log in to your account to add your own, private sources."
        )
        col1, col2 = st.columns(2)

        if col1.button("Sign In", icon="🔐", use_container_width=True):
            st.switch_page("pages/signin.py")

        if col2.button(
            "Create Account", type="primary", icon="👤", use_container_width=True
        ):
            st.switch_page("pages/signin.py")

        st.stop()

    subject = st.selectbox("Subject", subjects)
    " "

    book_name = st.selectbox(
        "Book name",
        ["School Book", "El-Moasser"],
        index=1,
        placeholder="Enter your book name / publisher",
    )
    " "

    uploaded_book = st.file_uploader("Upload a PDF of your **Book**:", type="pdf")
    " "

    uploaded_guide_answers = st.file_uploader(
        "Upload a PDF of your **Guide Answers Book**:", type="pdf"
    )

    ph = st.empty()
    " "
    if st.button(
        "Analyze & Add Book", type="primary", icon="➕", use_container_width=True
    ):
        if not (subject and book_name and uploaded_book and uploaded_guide_answers):
            ph.error("Missing Required Fields")
            st.stop()

        with st.spinner("Analyzing your documents...", show_time=True):
            add_source_service.add_book(
                clean_string(subject),
                book_name.lower(),
                uploaded_book.getvalue(),
                uploaded_guide_answers.getvalue(),
                gemini_model="gemini-3-flash-preview",
            )
            st.success("Source added successfuly!", icon="✅")


# Chat page
elif page == "chat":

    def right_align_user_msg():
        st.html(
            """
            <style>
                .stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {
                    display: flex;
                    flex-direction: row-reverse;
                    align-itmes: end;
                }

                [data-testid="stChatMessageAvatarUser"] + [data-testid="stChatMessageContent"] * {
                    text-align: right;
                }
            </style>
            """
        )

    def render_user_prompt(msg: dict):
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["msg"])

    def render_similar_questions(msg: dict, is_last_msg: bool = False):
        if msg["role"] == "assistant":
            ex_titles_icons = {
                "mcq": "📋",
                "complete": "✏️",
                "true_false": "✔️",
                "true_false_with_correction": "✔️",
                "correct_underlined": "🛠️",
                "text": "✍️",
            }

            with st.expander("🔍 Similar Questions", expanded=False):
                if msg["is_q_error"] == True:
                    st.error(
                        "An error occured while retrieving your answer. Check your internet connection and try again."
                    )

                else:
                    similar_questions = msg["similar_questions"]

                    if similar_questions:
                        msg_id = msg.get("id")

                        msgs_visible_counts = st.session_state["msgs_visible_counts"]

                        if msg_id not in msgs_visible_counts:
                            msgs_visible_counts[msg_id] = 3  # default

                        visible_limit = msgs_visible_counts[msg_id]
                        visible_similar_questions = similar_questions[:visible_limit]

                        for i, q_dict in enumerate(visible_similar_questions):

                            if i != 0:
                                "---"

                            if q_dict["point_type"] == "question":
                                ex_title: str = q_dict["ex_title"]
                                ex_type: str = q_dict["ex_type"]
                                question: str = q_dict["q_txt"]
                                answer: str = q_dict["a_txt"]

                                if ex_type in [
                                    "true_false",
                                    "true_false_with_correction",
                                ]:
                                    ex_title = (
                                        ex_title.replace("(T)", "(✓)")
                                        .replace("(t)", "(✓)")
                                        .replace("()", "Put (✓)")
                                        .replace("(X)", "(✗)")
                                        .replace("(x)", "(✗)")
                                    )

                                metadata = (
                                    f"📍 {q_dict["subject"].title()} , U{q_dict["unit_num"]} L{q_dict["lesson_num"]} , Page {q_dict["page"]} <br>"
                                    f"{ex_titles_icons[ex_type]} Ex {q_dict["ex_num"]}: {ex_title}"
                                    f"{":" if ex_title[-1] != ":" else ""}"
                                )
                                st.markdown(
                                    f"<p style='font-size: 1.2rem;'><strong>{metadata}</strong></p>",
                                    unsafe_allow_html=True,
                                )

                                if ex_type == "mcq":
                                    st.markdown(
                                        f"<p style='font-size: 1.1rem'> <strong>Q{q_dict["q_num"]}.</strong> {question}</p>",
                                        unsafe_allow_html=True,
                                    )

                                    for i, choice in enumerate(q_dict["mcq_choices"]):
                                        if i == int(answer):
                                            st.markdown(
                                                f"<span style='color: #FF0000;'>🔘 <strong><u>{choice}</u></strong></span>",
                                                unsafe_allow_html=True,
                                            )
                                        else:
                                            st.markdown(f"⚪ {choice}")

                                elif ex_type == "complete":
                                    answer = list(answer)
                                    it = iter(answer)
                                    question = re.sub(
                                        "_____",
                                        lambda x: f"<span style='color: #FF0000;'><strong><u>{next(it)}</u></strong></span>",
                                        question,
                                    )

                                    st.markdown(
                                        f"<p style='font-size: 1.1rem'> <strong>Q{q_dict["q_num"]}.</strong> {question}</p>",
                                        unsafe_allow_html=True,
                                    )

                                elif ex_type == "true_false":
                                    st.markdown(
                                        f"<p style='font-size: 1.1rem'> <strong>Q{q_dict["q_num"]}.</strong> {question}</p>",
                                        unsafe_allow_html=True,
                                    )
                                    if str(answer) == "True":
                                        st.write(f"A: ✅")
                                    elif str(answer) == "False":
                                        st.write(f"A: ❌")

                                elif ex_type == "true_false_with_correction":
                                    if str(answer[0]) == "True":
                                        st.markdown(
                                            f"<p style='font-size: 1.1rem'> <strong>Q{q_dict["q_num"]}.</strong> {question}</p>",
                                            unsafe_allow_html=True,
                                        )
                                        st.write(f"A: ✅")
                                    elif str(answer[0]) == "False":
                                        replacement = r"<u><strong>\1</strong></u>"
                                        question = re.sub(
                                            rf"(\b{answer[1]["mistake"]}\b)",
                                            replacement,
                                            question,
                                        )
                                        st.markdown(
                                            f"<p style='font-size: 1.1rem'> <strong>Q{q_dict["q_num"]}.</strong> {question}</p>",
                                            unsafe_allow_html=True,
                                        )

                                        st.markdown(
                                            f"A: ❌ / <span style='color: #FF0000;'><strong>{answer[1]["correction"]}</strong></span>",
                                            unsafe_allow_html=True,
                                        )

                                elif ex_type == "correct_underlined":
                                    mistake = answer["mistake"]
                                    question = question.replace(
                                        mistake,
                                        f"<u><strong>{mistake}</strong></u>",
                                    )
                                    st.markdown(
                                        f"<p style='font-size: 1.1rem'> <strong>Q{q_dict["q_num"]}.</strong> {question}</p>",
                                        unsafe_allow_html=True,
                                    )
                                    st.markdown(
                                        f"A: <span style='color: #FF0000;'><strong>{answer["correction"]}</strong></span>",
                                        unsafe_allow_html=True,
                                    )

                                else:
                                    st.markdown(
                                        f"<p style='font-size: 1.1rem'> <strong>Q{q_dict["q_num"]}.</strong> {question}</p>",
                                        unsafe_allow_html=True,
                                    )
                                    st.markdown(
                                        f"A: <span style='color: #FF0000;'><strong>{answer}</strong></span>",
                                        unsafe_allow_html=True,
                                    )

                        if is_last_msg and len(similar_questions) > visible_limit:
                            if st.button(
                                "Load More",
                                key=f"load_more_{msg_id}",
                            ):
                                st.session_state["load_more_clicked"] = True
                                st.session_state["msgs_visible_counts"][msg_id] += 3
                                st.rerun()

                    else:
                        st.write("**No Relevant Matches Found**")

    def render_messages(messages_data: list):

        # Custom HTML to right-align user messages
        right_align_user_msg()

        for msg_idx, msg in enumerate(messages_data):
            msg: dict

            render_user_prompt(msg)

            render_similar_questions(
                msg, is_last_msg=bool(msg_idx == len(messages_data) - 1)
            )

            if msg["role"] == "assistant":
                st.markdown(msg["ai_response"])

            " "
            " "

        # Scroll to bottom smoothly
        if not st.session_state.get("load_more_clicked", False):
            js = """
            <script>
                const allMessages = window.parent.document.querySelectorAll('[data-testid="stChatMessage"]');
                
                let lastUserMsg = null;
                for (const msg of allMessages) {
                    if (msg.querySelector('[data-testid="stChatMessageAvatarUser"]')) {
                        lastUserMsg = msg;
                    }
                }

                if (lastUserMsg) {
                    lastUserMsg.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    setTimeout(() => {
                        const el = window.parent.document.querySelector('section.stMain');
                        el.scrollBy({ top: -10, behavior: 'smooth' });
                    }, 300);
                } else {
                    const el = window.parent.document.querySelector('section.stMain');
                    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
                }
            </script>
            """
            components.html(js, height=0)

    # Custom HTML to add the "+" button beside st.chat_input
    theme = st_theme()
    st.markdown(
        f"""
        <style>
        div[data-testid="stLayoutWrapper"]:has(div[data-testid="stChatInput"]) {{
            position: fixed !important;
            bottom: 0 !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            width: {"70" if st.session_state.get("user_device_type", "pc") == "pc" else "100"}% !important;
            padding: 1rem 1rem 2.5rem !important;
            background: {theme["backgroundColor"] if theme else "#FFFFFF"} !important;
            z-index: 999 !important;
        }}

        body:has([data-testid="stSidebar"][aria-expanded="true"])
        div[data-testid="stLayoutWrapper"]:has(div[data-testid="stChatInput"]) {{
            left: calc(21rem + (100vw - 21rem - 70vw + 21rem * 0.7) / 2) !important;
            transform: none !important;
            width: calc((100vw - 21rem) * 0.7) !important;
            left: calc(21rem + (100vw - 21rem) * 0.15) !important;
        }}

        .main .block-container {{
            padding-bottom: 80px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        col1, col2 = st.columns([0.08, 0.92], vertical_alignment="center")
        with col1:
            with st.popover("", icon="➕", help="Apply filters to get better results"):
                menu_choice = st.session_state.get("menu_choice", "all_grades")

                # If user came from "All Grades", show all 4 filters
                if menu_choice == "all_grades":
                    grade_f_options = ["♾️ All", "📓 Preparatory 2"]
                    grade_f_index = 0
                    try:
                        if st.session_state.get("user"):
                            grade_f_index = grade_f_options.index(
                                get_key_by_value(
                                    grades, st.session_state["user"]["grade"]
                                )
                            )
                    except:
                        pass

                    grade_filter = st.selectbox(
                        "🎓 Grade", grade_f_options, grade_f_index
                    )

                    subject_filter = st.selectbox("📚 Subject", ["♾️ All", "🔬 Science"])

                # If user came from specific subject, only show Unit/Lesson and display grade/subject as locked
                else:
                    if st.session_state.get("user"):
                        user_grade_long = get_key_by_value(
                            grades, st.session_state["user"]["grade"]
                        )
                        selected_subject = menu_choice

                        subjects_codes = [
                            clean_string(subj).lower() for subj in subjects
                        ]
                        st.info(
                            f"{user_grade_long} • {subjects[subjects_codes.index(selected_subject)]}",
                        )

                        # Set these for filter logic
                        grade_filter = user_grade_long
                        subject_filter = selected_subject
                    else:
                        grade_filter = "♾️ All"
                        subject_filter = "♾️ All"

                unit_num_filter = st.selectbox(
                    "📌 Unit",
                    ["♾️ All", 1, 2, 3, 4],
                    accept_new_options=True,
                )
                lesson_num_filter = st.selectbox(
                    "📝 Lesson",
                    ["♾️ All", 1, 2, 3, 4],
                    accept_new_options=True,
                )

        with col2:
            user_query = st.chat_input("Ask something...")

    def get_filters(point_type: Literal["question", "explanation"] = "explanation"):
        filters = []
        for key, value in {
            "point_type": point_type,
            "grade": str(grade_filter),
            "subject": clean_string(str(subject_filter)),
            "unit_num": clean_string(str(unit_num_filter)),
            "lesson_num": clean_string(str(lesson_num_filter)),
        }.items():

            if value and clean_string(value).lower() != "all":
                if key in ["unit_num", "lesson_num"]:
                    value = int(value)
                elif key == "grade":
                    value = grades[value]

                filters.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )

        return Filter(must=filters)

    # Render previous msgs if found
    render_messages(st.session_state.get("messages_data", []))

    if user_query and user_query.strip():

        # Step 1: Initialize chat if needed
        username = (
            st.session_state.get("user", {}).get("username")
            if st.session_state.get("user")
            else None
        )
        if not st.session_state.get("current_chat_id") and username:
            st.session_state["current_chat_id"] = chat_service.create_chat(username)

        # Save user message and render it
        messages_data: list = st.session_state.get("messages_data", [])

        user_msg_dict = {"role": "user", "msg": user_query}
        messages_data.append(user_msg_dict)

        # Save to database
        if username and st.session_state.get("current_chat_id"):
            chat_service.save_message(
                username, st.session_state["current_chat_id"], "user", user_query
            )

        # Render user message
        right_align_user_msg()
        with st.chat_message("user"):
            st.write(user_query)

        # Step 2: Save similar questions and render it
        assistant_msg_id = str(uuid.uuid4())
        assistant_msg_dict = {
            "id": assistant_msg_id,
            "role": "assistant",
            "similar_questions": [],
            "ai_response": "",
            "is_q_error": False,
            "is_ai_error": False,
        }
        messages_data.append(assistant_msg_dict)

        last_msg_idx = len(messages_data) - 1

        is_q_error = False
        questions_payloads = []

        with st.spinner("Retrieving similar questions..."):
            try:
                # 1. Retrieve similar questions
                questions_payloads = rag_service.search(
                    user_query,
                    limit=12,
                    score_threshold=0.8,
                    query_filter=get_filters("question"),
                )

                # Update similar_questions in session state
                messages_data[last_msg_idx]["similar_questions"] = questions_payloads

            except Exception as e:
                is_q_error = True
                messages_data[last_msg_idx]["is_q_error"] = True
                st.write(e)

        st.session_state["load_more_clicked"] = False

        # Render similar questions
        render_similar_questions(assistant_msg_dict, is_last_msg=True)

        # Step 3: Save AI response and stream it
        with st.spinner("Generating..."):
            # try:
            explanation_payloads = rag_service.search(
                user_query,
                limit=10,
                score_threshold=0.5,
                query_filter=get_filters("explanation"),
            )

            # Get all the included lessons ids
            lesson_ids = []
            for exp in explanation_payloads:
                if exp["lesson_id"] not in lesson_ids:
                    lesson_ids.append(exp["lesson_id"])

            # Get the lessons sources concatenated texts
            sources_text = rag_service.get_sources(lesson_ids)

            # Get chat history for model context
            chat_history = []

            for m in st.session_state.get("messages_data", []):
                if m["role"] == "user":
                    chat_history.append({"role": "user", "content": m["msg"]})
                else:
                    chat_history.append(
                        {"role": "assistant", "content": m["ai_response"]}
                    )

            if chat_history and chat_history[-1]["role"] == "user":
                chat_history = chat_history[:-1]

            # --- Rendering the AI response (2 ways) ---

            is_first_prompt = (
                chat_history
                and len(chat_history) <= 2
                and not chat_history[-1].get("content")
            )

            if is_first_prompt:
                # FIRST - get response, suggested chat title
                json_response = rag_service.generate_response(
                    user_query, sources_text, chat_history, get_chat_title=True
                )

                full_response: str = json_response["response"]
                st.markdown(full_response)

                # Update ss with full response
                messages_data[last_msg_idx]["ai_response"] = full_response

                # Save to DB
                if username and st.session_state.get("current_chat_id"):
                    chat_service.save_message(
                        username=username,
                        chat_id=st.session_state["current_chat_id"],
                        role="assistant",
                        content=full_response,
                        similar_questions=questions_payloads,
                    )

                if username:
                    chat_service.update_title(
                        username,
                        st.session_state["current_chat_id"],
                        json_response["suggested_chat_title"],
                    )

            else:
                # SECOND - stream response

                # Create a generator that yields chunks and collects full response
                def stream_and_collect():
                    full_response = ""

                    for chunk in rag_service.generate_response_stream(
                        user_query, sources_text, chat_history
                    ):
                        full_response += chunk
                        yield chunk

                    # Update ss with full response
                    messages_data[last_msg_idx]["ai_response"] = full_response

                    if username and st.session_state.get("current_chat_id"):
                        chat_service.save_message(
                            username=username,
                            chat_id=st.session_state["current_chat_id"],
                            role="assistant",
                            content=full_response,
                            similar_questions=questions_payloads,
                        )

                # Stream the AI response
                st.write_stream(stream_and_collect())

            # Update messages_data ss
            st.session_state["messages_data"] = messages_data

        # except Exception as e:
        #     messages_data[last_msg_idx]["is_ai_error"] = True
        #     st.session_state["messages_data"] = messages_data
        #     st.error(f"Error: {e}")

    elif not st.session_state.get("messages_data"):
        st.header("How can I help you today?", text_alignment="center", anchor=False)
