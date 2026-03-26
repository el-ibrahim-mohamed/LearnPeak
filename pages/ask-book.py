import streamlit as st
from streamlit_shortcuts import shortcut_button
from streamlit_theme import st_theme
from typing import Literal
import re
import uuid


# Defining Functions
def clean_string(input_str: str):
    return (
        "".join(char for char in input_str if char.isalnum() or char.isspace())
        .strip()
        .replace("  ", " ")
    )


def map_grades(grade: str, to: Literal["short", "long"] = "short"):
    grade_mapping = {
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

    if to == "short":
        return grade_mapping[grade]

    elif to == "long":
        return [k for k, v in grade_mapping.items() if v == grade][0]


if "msgs_visible_counts" not in st.session_state:
    st.session_state["msgs_visible_counts"] = {}

# Loading the RAG system
st.sidebar.title("🧠 Learn Peak :blue[RAG] System")
with st.spinner("Loading Learn Peak RAG System...", show_time=True):
    with st.spinner("Importing services..."):
        from qdrant_client import models
        from rag.embedding_service import EmbeddingService
        from rag.qdrant_service import QdrantService
        from rag.rag_service import RagService, AddSource

    # Initialize Services (Cached)
    @st.cache_resource
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
                models.PayloadSchemaType.KEYWORD,
            )

        for payload_key in ["term", "unit_num", "lesson_num", "page"]:
            qdrant_service.create_payload_index(
                qdrant_service.collection_name,
                payload_key,
                models.PayloadSchemaType.INTEGER,  # <-- changed
            )

        return RagService(qdrant_service, embedding_service)

    rag_service = init_services()

with st.sidebar:
    " "
    if st.button("Add Source (Beta)", icon="➕", use_container_width=True):
        st.session_state["rag_page"] = "add_source"

    if shortcut_button(
        "New Chat",
        "ctrl+k",
        hint=False,
        type="primary",
        icon="📝",
        use_container_width=True,
        help="Ctrl + K",
    ):
        st.session_state["rag_page"] = "chat"
        st.session_state["messages_data"] = []

    st.caption("Your chats")


page = st.session_state.get("rag_page", "chat")

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
grades = [
    "🎨 kG 1",
    "🎨 KG 2",
    "🎒 Primary 1",
    "🎒 Primary 2",
    "🎒 Primary 3",
    "🎒 Primary 4",
    "🎒 Primary 5",
    "🎒 Primary 6",
    "📓 Preparatory 1",
    "📓 Preparatory 2",
    "📓 Preparatory 3",
    "🔬 Secondary 1",
    "🔬 Secondary 2",
    "🔬 Secondary 3",
]

# Add source page
if page == "add_source":
    st.title("➕ Add a Source")
    "---"

    st.error("This feature is currently unavailable!")
    st.stop()
    
    if st.session_state.get("user"):
        if "add_source_service" not in st.session_state:
            with st.spinner("Loading Add Source Service..."):
                st.session_state["add_source_service"] = AddSource(
                    st.session_state["client"],
                    rag_service,
                    st.session_state["user"]["grade"],
                )
        add_source_service = st.session_state["add_source_service"]

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
                clean_string(subject).lower(),
                book_name.lower(),
                uploaded_book.getvalue(),
                uploaded_guide_answers.getvalue(),
                gemini_model = "gemini-3-flash-preview"
            )
            st.success("Source added successfuly!", icon="✅")


# Chat page
elif page == "chat":

    def render_messages(messages_data: list):
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

        last_assistant_id = None
        for msg in reversed(messages_data):
            if msg["role"] == "assistant":
                last_assistant_id = msg.get("id")
                break

        ex_titles_icons = {
            "mcq": "📋",
            "complete": "✏️",
            "true_false": "✔️",
            "true_false_with_correction": "✔️",
            "correct_underlined": "🛠️",
            "text": "✍️",
        }

        for msg in messages_data:
            msg: dict
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["msg"])
            else:

                if msg["is_error"] == True:
                    st.error(
                        "An error occured while retrieving your answer. Check your internet connection and try again."
                    )

                else:
                    results = msg["results"]

                    if results:
                        msg_id = msg.get("id")

                        msgs_visible_counts = st.session_state["msgs_visible_counts"]

                        if msg_id not in msgs_visible_counts:
                            msgs_visible_counts[msg_id] = 3  # default

                        visible_limit = msgs_visible_counts[msg_id]
                        visible_results = results[:visible_limit]

                        for i, q_dict in enumerate(visible_results):

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
                                    f"📍 {q_dict["subject"].title()} , Unit {q_dict["unit_num"]} , Lesson {q_dict["lesson_num"]} , Page {q_dict["page"]} <br>"
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
                                            st.markdown(f"🔘 **{choice}**")
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
                                        mistake, f"<u><strong>{mistake}</strong></u>"
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

                        if msg_id == last_assistant_id and len(results) > visible_limit:
                            if st.button(
                                "Load More",
                                key=f"load_more_{msg_id}",
                            ):
                                st.session_state["load_more_clicked"] = True
                                st.session_state["msgs_visible_counts"][msg_id] += 3
                                st.rerun()

                    else:
                        st.write("**No Relevant Matches Found**")

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
            st.components.v1.html(js, height=0)

    theme = st_theme()

    st.markdown(
        f"""
        <style>
        div[data-testid="stLayoutWrapper"]:has(div[data-testid="stChatInput"]) {{
            position: fixed !important;
            bottom: 0 !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            width: {"70" if st.session_state["user_device_type"] == "pc" else "100"}% !important;
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
                grade_f_options = ["♾️ All", *grades]
                grade_f_index = 0
                if st.session_state.get("user"):
                    grade_f_index = grade_f_options.index(
                        map_grades(st.session_state["user"]["grade"], to="long")
                    )

                grade_filter = st.selectbox(
                    "🎓 Grade", grade_f_options, index=grade_f_index
                )

                subject_filter = st.selectbox("📚 Subject", ["♾️ All", *subjects])
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

    if user_query and user_query.strip():
        with st.spinner("Thinking..."):
            is_error = False
            results_payloads = []

            try:
                must_filters = []
                for key, value in {
                    "point_type": "question",
                    "grade": str(grade_filter),
                    "subject": clean_string(str(subject_filter)).lower(),
                    "unit_num": clean_string(str(unit_num_filter)),
                    "lesson_num": clean_string(str(lesson_num_filter)),
                }.items():
                    if value and clean_string(value).lower() != "all":
                        if key in ["unit_num", "lesson_num"]:
                            value = int(value)
                        elif key == "grade":
                            value = map_grades(value)

                        must_filters.append(
                            models.FieldCondition(
                                key=key,
                                match=models.MatchValue(value=value),
                            )
                        )

                questions_filter = models.Filter(must=must_filters)
                results_payloads = rag_service.search(
                    user_query, query_filter=questions_filter
                )
                st.session_state["load_more_clicked"] = False

            except Exception as e:
                is_error = True
                st.write(e)

        user_msg_dict = {"role": "user", "msg": user_query}
        assistant_msg_dict = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "is_error": is_error,
            "results": results_payloads,
        }

        messages_data: list = st.session_state.get("messages_data", [])
        messages_data.append(user_msg_dict)
        messages_data.append(assistant_msg_dict)
        st.session_state["messages_data"] = messages_data

    if st.session_state.get("messages_data"):
        render_messages(st.session_state.get("messages_data"))
    else:
        st.header("How can I help you today?", text_alignment="center")
