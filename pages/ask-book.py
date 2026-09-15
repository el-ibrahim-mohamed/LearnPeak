import streamlit as st
import re
from datetime import datetime
import unicodedata
from streamlit_shortcuts import shortcut_button
from services.rag.chat_service import ChatService
from config import *

# Set page config
st.set_page_config(
    page_title="Ask Your Book - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)

user: dict = st.session_state.get("user", {})

# Loading the RAG system
st.sidebar.title("🧠 LearnPeak :blue[RAG] System")
with st.spinner("Loading LearnPeak RAG System...", show_time=True):
    with st.spinner("Importing services..."):
        from qdrant_client.models import (
            PayloadSchemaType,
            Filter,
            FieldCondition,
            MatchAny,
        )
        from services.rag.embedding_service import EmbeddingService
        from services.rag.qdrant_service import QdrantService
        from services.rag.rag_service import RagService

    # Initialize Services
    @st.cache_resource
    def init_qdrant_service(vector_size: int):

        qdrant_service = QdrantService(
            url=st.secrets["qdrant"]["URL"],
            api_key=st.secrets["qdrant"]["API_KEY"],
            vector_size=vector_size,
        )

        qdrant_service.ensure_collection_exists()

        for payload_key in [
            "id",
            "batch_id",
            "country",
            "education",
            "book_publisher",
            "grade",
            "subject",
        ]:
            qdrant_service.create_payload_index(
                qdrant_service.collection_name,
                payload_key,
                field_schema=PayloadSchemaType.KEYWORD,
            )

        for payload_key in [
            "term",
            "unit_num",
            "lesson_num",
            "page_num",
        ]:
            qdrant_service.create_payload_index(
                qdrant_service.collection_name,
                payload_key,
                field_schema=PayloadSchemaType.INTEGER,
            )

        return qdrant_service

    qdrant_service = init_qdrant_service(EMBEDDING_VECTOR_SIZE)

    @st.cache_resource
    def init_rag_services():

        # Embedding model
        embedding_service = EmbeddingService()

        # RagService
        rag_service = RagService(
            qdrant_service=qdrant_service,
            embedding_service=embedding_service,
            gemini_client=st.session_state["client"],
        )

        return rag_service

    rag_service = init_rag_services()

if user and user.get("uid"):
    chat_service = ChatService(st.session_state.get("root_ref"), user["uid"])

if "sidebar_update_key" not in st.session_state:
    st.session_state["sidebar_update_key"] = 0


@st.cache_data(ttl=3600, show_spinner=False)  # Caches for 1 hour
def get_cached_chats(user_uid: str):
    return chat_service.get_chats(user_uid)


def clear_cached_chats():
    get_cached_chats.clear()
    st.session_state["chats"] = None


@st.fragment
def render_sidebar_chats():
    if user:

        chats = st.session_state.get("chats")

        if not chats and chats != []:
            chats = get_cached_chats(user["uid"])
            st.session_state["chats"] = chats

        if chats:
            counter = st.session_state.get("sidebar_update_key", 0)
            for chat in chats:
                # Chat name, rename, and delete columns
                col1, col2, col3 = st.columns(
                    [0.65, 0.20, 0.15], vertical_alignment="center"
                )

                # Open chat button
                with col1:
                    # Max chat title length: 35 characters
                    chat_title = chat["title"]
                    chat_title = (
                        chat_title if len(chat_title) <= 35 else f"{chat_title[:35]}.."
                    )

                    if st.button(
                        chat_title,
                        key=f"chat_{chat['id']}_{counter}",
                        use_container_width=True,
                    ):
                        # Load messages from Firebase
                        db_chat_messages = chat_service.get_chat_messages(chat["id"])

                        # 4. Save to session state
                        st.session_state["rag_page"] = "chat"
                        st.session_state["current_chat_id"] = chat["id"]
                        st.session_state["messages_data"] = db_chat_messages
                        st.session_state["scroll_to_bottom"] = True
                        st.rerun()

                # Rename chat button
                with col2:
                    with st.popover("", icon="✏️"):
                        new_chat_title = st.text_input(
                            "New chat name",
                            value=chat["title"],
                            icon="✍️",
                            label_visibility="collapsed",
                            key=f"rename_chat_{chat['id']}_{counter}",
                        )

                        # Triggers auto-save on Enter or tap/click away
                        if new_chat_title.strip() and new_chat_title != chat["title"]:
                            chat_service.update_title(
                                chat["id"],
                                new_chat_title.strip(),
                            )
                            clear_cached_chats()
                            st.rerun(scope="fragment")

                # Delete chat button
                with col3:
                    if st.button("", key=f"del_{chat['id']}_{counter}", icon="🗑️"):
                        chat_service.delete_chat(chat["id"])
                        clear_cached_chats()
                        st.session_state["rag_page"] = "chat"
                        st.session_state["messages_data"] = []
                        st.session_state["current_chat_id"] = None
                        st.rerun()

        else:
            st.info("No chats found. Create your first one!")

    else:
        st.info("Sign in to save your chats.")


with st.sidebar:
    # Menu Page button
    if st.button("Menu", icon="📋", use_container_width=True):
        st.session_state["rag_page"] = "menu"
        st.session_state["messages_data"] = []
        st.session_state["current_chat_id"] = None

    # New chat shortcut button
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

    # Load and display previous chats
    st.caption("Your chats")

    # 1. Detect if the user JUST submitted a first prompt (before reaching the bottom)
    current_chat_input = st.session_state.get("main_chat_input")
    is_creating_new_chat = bool(current_chat_input) and not st.session_state.get(
        "current_chat_id"
    )

    # 2. Conditionally apply the placeholder
    if is_creating_new_chat:
        chat_history_placeholder = st.empty()
        with chat_history_placeholder.container():
            render_sidebar_chats()
    else:
        # NORMAL RUN: Native rendering. Streamlit diffs this perfectly = NO FLICKER!
        render_sidebar_chats()


# Determine the page to show (menu, chat)
page = st.session_state.get("rag_page", "menu")

# Menu page
if page == "menu":
    st.title("📚 Choose your subject", anchor=False)
    "---"

    # Custom CSS for the subjects buttons
    def button_container_html(btn_key):
        st.html(f"""
            <style>
            .st-key-{btn_key} button {{
                height: auto;
                padding: 20px;
                border-radius: 12px;
                /* Uses Streamlit's secondary bg/border token or translucent white/black */
                border: 1px solid rgba(128, 128, 128, 0.2); 
                text-align: center;
                display: block;
                transition: all 0.3s ease-in-out;
                white-space: pre-wrap;
            }}

            .st-key-{btn_key} button:hover {{
                /* 1. Theme accent color for the border */
                border-color: var(--primary-color);
                
                /* 2. Slightly brighten/darken the button WITHOUT hardcoding background-color */
                filter: brightness(0.95);
                
                /* 3. Theme-aware shadow using semi-transparent black */
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
                transform: translateY(-2px);
            }}

            .st-key-{btn_key} button p {{
                font-size: 15px;
                margin: 0;
                line-height: 1.5;
            }}
            </style>
            """)

    st.subheader("🌍 All Grades", anchor=False)
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

    if user:
        " "
        user_grade_code = user.get("grade", "prim4")
        user_grade_long = get_key_by_value(GRADES, user_grade_code) or "Your Grade"

        st.subheader(user_grade_long, anchor=False)

        # Retrieve grade-specific subjects
        grade_subjects_dict = get_subjects_for_grade(user_grade_code)
        subjects_list = list(grade_subjects_dict.keys())

        for i in range(0, len(subjects_list), 2):
            col1, col2 = st.columns(2)

            # First item in row
            subject = subjects_list[i]
            subj_code = grade_subjects_dict[subject]
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
            if i + 1 < len(subjects_list):
                subject = subjects_list[i + 1]
                subj_code = grade_subjects_dict[subject]
                btn_key = f"subject_{subj_code}"

                with col2:
                    button_container_html(btn_key)
                    if st.button(subject, use_container_width=True, key=btn_key):
                        st.session_state["menu_choice"] = subj_code
                        st.session_state["rag_page"] = "chat"
                        st.session_state["messages_data"] = []
                        st.session_state["current_chat_id"] = None
                        st.rerun()

    else:
        st.space()
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


# Chat page
elif page == "chat":

    def right_align_user_avatar():
        st.html("""
            <style>
                .stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {
                    display: flex;
                    flex-direction: row-reverse;
                    align-items: end;
                }
            </style>
            """)

    right_align_user_avatar()

    def get_text_direction(text: str) -> str:
        """Returns 'rtl' if there are more RTL characters than LTR, otherwise 'ltr'."""
        rtl_count = 0
        ltr_count = 0

        for char in text:
            direction = unicodedata.bidirectional(char)
            if direction in ("R", "AL"):
                rtl_count += 1
            elif direction == "L":
                ltr_count += 1

        return "rtl" if rtl_count > ltr_count else "ltr"

    def render_user_prompt(msg: str):
        direction = get_text_direction(msg)
        text_alignment = "right" if direction == "rtl" else "left"
        with st.chat_message("user"):
            st.markdown(msg, text_alignment=text_alignment)

    def render_ai_response(response: str):
        st.markdown(response, anchors=False)

    def render_messages(messages_data: list):
        for msg in messages_data:
            msg: dict

            if msg["role"] == "user":
                render_user_prompt(msg["content"])

            if msg["role"] == "assistant":
                render_ai_response(msg["content"])

            " "
            " "

    def scroll_to_bottom():
        st.html(
            f"""
            <script>
            const main = window.parent.document.querySelector(
                'section[data-testid="stMain"]'
            );

            if (main) {{
                main.scrollTo({{
                    top: main.scrollHeight,
                }});
            }}
            </script>
            """,
            unsafe_allow_javascript=True,
        )

    with st.bottom:
        col1, col2 = st.columns([0.08, 0.92], vertical_alignment="center")
        with col1:
            with st.popover("", icon="➕", help="Apply filters to get better results"):
                menu_choice = st.session_state.get("menu_choice", "all_grades")

                grade_options = list(GRADES.keys())
                default_grade = []
                if user and user.get("grade"):
                    user_grade_label = get_key_by_value(GRADES, user["grade"])
                    if user_grade_label and user_grade_label in grade_options:
                        default_grade = [user_grade_label]

                grade_filter = st.multiselect(
                    "🎓 Grade",
                    grade_options,
                    default=default_grade,
                )

                # Determine available subjects based on selected grades in filter
                if grade_filter:
                    allowed_codes = set()
                    for g_label in grade_filter:
                        g_code = GRADES.get(g_label)
                        if g_code:
                            allowed_codes.update(GRADE_SUBJECTS.get(g_code, []))

                    available_subjects_dict = {
                        k: v for k, v in SUBJECTS.items() if v in allowed_codes
                    }
                else:
                    available_subjects_dict = SUBJECTS

                subject_options = list(available_subjects_dict.keys())

                # Determine default subject selection
                default_subject = []
                if menu_choice != "all_grades":
                    chosen_subject_label = get_key_by_value(SUBJECTS, menu_choice)
                    if chosen_subject_label and chosen_subject_label in subject_options:
                        default_subject = [chosen_subject_label]

                subject_filter = st.multiselect(
                    "📚 Subject",
                    subject_options,
                    default=default_subject,
                )

                unit_num_filter = st.multiselect(
                    "📌 Unit",
                    UNIT_OPTIONS,
                    default=[],
                )

                lesson_num_filter = st.multiselect(
                    "📝 Lesson",
                    LESSON_OPTIONS,
                    default=[],
                )

        with col2:
            user_input = st.chat_input(
                "Ask something...",
                key="main_chat_input",
                max_upload_size=45,
                accept_file="multiple",
                file_type=[
                    "pdf",
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                    "txt",
                    "md",
                    "csv",
                    "json",
                    "docx",
                    "pptx",
                    "xlsx",
                ],
                submit_mode="disable",
            )

    def get_filters():
        filters = []

        filter_values = {
            "grade": grade_filter,
            "subject": subject_filter,
            "unit_num": unit_num_filter,
            "lesson_num": lesson_num_filter,
        }

        for key, values in filter_values.items():
            if not values:
                continue

            if key == "grade":
                values = [GRADES[value] for value in values]

            elif key == "subject":
                values = [SUBJECTS[value] for value in values]

            elif key in ["unit_num", "lesson_num"]:
                values = [int(value) for value in values]

            filters.append(
                FieldCondition(
                    key=key,
                    match=MatchAny(any=values),
                )
            )

        return Filter(must=filters) if filters else None

    # Render previous msgs if found
    render_messages(st.session_state.get("messages_data", []))

    # Scroll to bottom if just opened the chat
    if st.session_state.get("scroll_to_bottom"):
        print(st.session_state["scroll_to_bottom"])
        scroll_to_bottom()
        st.session_state["scroll_to_bottom"] = False

    if user_input:

        # Get text and attachments
        user_query = user_input.text
        uploaded_files = user_input.files

        # Step 1: Initialize chat if needed
        if user and not st.session_state.get("current_chat_id"):
            clear_cached_chats()
            st.session_state["current_chat_id"] = chat_service.create_chat()

        # Save user message and render it
        messages_data: list = st.session_state.get("messages_data", [])

        user_msg_dict = {"role": "user", "content": user_query}
        messages_data.append(user_msg_dict)

        # Save user msg timestamp
        user_timestamp = datetime.now().isoformat()

        # Render user message and scroll to bottom
        render_user_prompt(user_query)
        scroll_to_bottom()

        # Step 3: Save AI response and stream it
        with st.spinner("Generating..."):
            # Determine whether the user selected a specific lesson scope
            full_lesson_source = (
                bool(grade_filter)
                and bool(subject_filter)
                and len(unit_num_filter) == 1
                and bool(lesson_num_filter)
            )

            # Get the enriched sources text
            if full_lesson_source:
                sources_text = rag_service.scroll_from_filters(get_filters())
            else:
                # Determining the enriching scope
                LESSON_KEYWORDS = {
                    # English
                    "lesson",
                    "lessons",
                    "unit",
                    "units",
                    "chapter",
                    "chapters",
                    "summarize",
                    "summary",
                    "overview",
                    # Arabic
                    "درس",
                    "الدرس",
                    "الوحدة",
                    "وحدة",
                    "الفصل",
                    "ملخص",
                    "لخص",
                }

                words = set(re.findall(r"\b\w+\b", user_query.lower()))
                enriching_scope = "lesson" if words & LESSON_KEYWORDS else "page"

                chunks_payloads = rag_service.search(
                    user_query,
                    limit=10,
                    score_threshold=0.5,
                    query_filter=get_filters(),
                )

                # Get the lessons sources concatenated texts
                sources_text = rag_service.enrich_sources(
                    chunks_payloads, scope=enriching_scope
                )

            # Get chat history for model context
            chat_history = st.session_state.get("messages_data", [])

            # Build student info dict
            student_info = {}
            if user:
                student_info = {"name": user["full_name"]}

            # --- Rendering the AI response (2 ways) ---
            is_first_prompt = bool(chat_history)

            if is_first_prompt:
                # FIRST - get response, suggested chat title
                json_response = rag_service.generate_response(
                    user_query,
                    sources_text,
                    uploaded_files,
                    chat_history,
                    student_info,
                )

                full_response: str = json_response["response"]
                render_ai_response(full_response)

                # Update ss with full response
                assistant_msg_dict = {
                    "role": "assistant",
                    "content": full_response,
                }
                messages_data.append(assistant_msg_dict)

                # Save to DB
                if user and st.session_state.get("current_chat_id"):
                    chat_service.save_message(
                        chat_id=st.session_state["current_chat_id"],
                        user_prompt=user_query,
                        user_timestamp=user_timestamp,
                        ai_response=full_response,
                    )

                if user:
                    clear_cached_chats()
                    chat_service.update_title(
                        st.session_state["current_chat_id"],
                        json_response["suggested_chat_title"],
                    )
                    st.session_state["sidebar_update_key"] += 1
                    # Overwrite the placeholder instantly
                    if is_creating_new_chat:
                        with chat_history_placeholder.container():
                            render_sidebar_chats()

            else:
                # SECOND - stream response

                # Create a generator that yields chunks and collects full response
                def stream_and_collect():
                    full_response = ""

                    for chunk in rag_service.generate_response_stream(
                        user_query,
                        sources_text,
                        uploaded_files,
                        chat_history,
                        student_info,
                    ):
                        full_response += chunk
                        yield chunk

                    # Update ss with full response
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": full_response,
                    }
                    messages_data.append(assistant_msg_dict)

                    if user and st.session_state.get("current_chat_id"):
                        chat_service.save_message(
                            chat_id=st.session_state["current_chat_id"],
                            user_prompt=user_query,
                            user_timestamp=user_timestamp,
                            ai_response=full_response,
                        )

                # Stream the AI response
                st.write_stream(stream_and_collect())

            # Update messages_data ss
            st.session_state["messages_data"] = messages_data

        # except Exception as e:
        #     messages_data[-1]["is_ai_error"] = True
        #     st.session_state["messages_data"] = messages_data
        #     st.error(f"Error: {e}")

    elif not st.session_state.get("messages_data"):
        st.header("How can I help you today?", text_alignment="center", anchor=False)
