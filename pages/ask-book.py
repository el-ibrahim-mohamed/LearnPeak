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
            "category",
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

    # Gemini Power Badge / Announcement Card
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, rgba(66, 133, 244, 0.08) 0%, rgba(155, 114, 203, 0.08) 100%);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 12px;
            padding: 14px 18px;
            margin-top: 10px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        ">
            <span style="font-size: 22px;">✨</span>
            <div style="line-height: 1.4;">
                <span style="font-weight: 600; font-size: 15px; color: var(--text-color);">Powered by Google Gemini's Latest AI Models</span><br/>
                <span style="font-size: 13px; opacity: 0.85; color: var(--text-color);">
                    Instantly query your exact school textbooks and curriculum with high precision.
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    ERROR_MESSAGE = (
        "An error occurred while generating your response. "
        "Please try again later or reload the app."
    )

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

    def render_file_attachments(files_list: list[dict]):
        """Renders small, stylized attachment badges above user chat messages."""
        if not files_list:
            return

        # Map categories to visual icons
        icon_map = {"pdf": "📄", "image": "🖼️", "code": "💻", "document": "📝"}

        cols = st.columns(min(len(files_list), 4))
        for idx, file_data in enumerate(files_list):
            category = file_data.get("file_type_category", "document")
            icon = icon_map.get(category, "📎")
            file_name = file_data.get("file_name", "Attachment")

            # Truncate long file names for UI tidiness
            display_name = file_name[:20] + "..." if len(file_name) > 23 else file_name

            with cols[idx % 4]:
                st.caption(f"{icon} **{display_name}**")

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
                if msg.get("files"):
                    render_file_attachments(msg["files"])

                render_user_prompt(msg["content"])

            if msg["role"] == "assistant":
                if msg.get("is_error"):
                    st.error(ERROR_MESSAGE)
                else:
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

    @st.fragment
    def render_filter_popover():
        with st.popover("", icon="➕", help="Apply filters to get better results"):
            menu_choice = st.session_state.get("menu_choice", "all_grades")

            # In render_filter_popover() inside pages/ask-book.py:
            grade_options = ["All"] + list(GRADES.keys())
            default_index = 0

            if user and user.get("grade"):
                user_grade_label = get_key_by_value(GRADES, user["grade"])
                if user_grade_label in GRADES:
                    default_index = grade_options.index(user_grade_label)

            selected_grade_label = st.selectbox(
                "🎓 Grade",
                options=grade_options,
                index=default_index,
                key="filter_grade_select",
            )

            # Store selected grade code in session state (or All)
            grade_filter = (
                GRADES[selected_grade_label] if selected_grade_label != "All" else None
            )

            st.session_state["filter_grade"] = grade_filter

            # SUBJECT
            if selected_grade_label:
                allowed_codes = set()
                g_code = GRADES.get(selected_grade_label)
                if g_code:
                    allowed_codes.update(GRADE_SUBJECTS.get(g_code, []))

                available_subjects_dict = {
                    k: v for k, v in SUBJECTS.items() if v in allowed_codes
                }
            else:
                available_subjects_dict = SUBJECTS

            subject_options = list(available_subjects_dict.keys())

            default_subject = []
            if menu_choice != "all_grades":
                chosen_subject_label = get_key_by_value(SUBJECTS, menu_choice)
                if chosen_subject_label and chosen_subject_label in subject_options:
                    default_subject = [chosen_subject_label]

            selected_subjects = st.multiselect(
                "📚 Subject",
                subject_options,
                default=default_subject,
                key="filter_subject",
                filter_mode=None,
            )

            # CATEGORY
            is_english_selected = any(
                subj.lower() == "english" or SUBJECTS.get(subj) == "english"
                for subj in selected_subjects
            )

            # Determine available categories from config.py
            if is_english_selected:
                cat_dict = ENGLISH_CATEGORIES
            else:
                cat_dict = CATEGORIES

            category_options = list(cat_dict.keys())

            selected_category_label = st.selectbox(
                "🏷️ Category",
                options=category_options,
                index=0,
                key="filter_category",
            )
            st.session_state["filter_category_code"] = cat_dict.get(selected_category_label)

            # UNIT
            # Default options are 1-4, but user can type and add higher numbers (e.g., 7, 8, 9, 10)
            selected_units = st.multiselect(
                "📌 Unit",
                options=UNIT_OPTIONS,
                key="filter_unit_raw",
                accept_new_options=True,
            )

            # Sanitize Unit input: keep only numeric strings
            valid_units = [u for u in selected_units if str(u).isdigit()]
            if len(valid_units) != len(selected_units):
                st.caption("⚠️ Only numbers are allowed for Units.")
            st.session_state["filter_unit"] = valid_units

            # LESSON
            selected_lessons = st.multiselect(
                "📝 Lesson",
                options=LESSON_OPTIONS,
                key="filter_lesson_raw",
                accept_new_options=True,
            )

            # Sanitize Lesson input: keep only numeric strings
            valid_lessons = [l for l in selected_lessons if str(l).isdigit()]
            if len(valid_lessons) != len(selected_lessons):
                st.caption("⚠️ Only numbers are allowed for Lessons.")
            st.session_state["filter_lesson"] = valid_lessons

    with st.bottom:
        col1, col2 = st.columns([0.08, 0.92], vertical_alignment="center")
        with col1:
            render_filter_popover()

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

        # Retrieve current filter states
        filter_grade_code = st.session_state.get("filter_grade")
        selected_subjects = st.session_state.get("filter_subject", [])
        category_code = st.session_state.get("filter_category_code")
        unit_values = st.session_state.get("filter_unit", [])
        lesson_values = st.session_state.get("filter_lesson", [])

        filter_values = {
            "unit_num": [int(u) for u in unit_values if str(u).isdigit()],
            "lesson_num": [int(l) for l in lesson_values if str(l).isdigit()],
        }

        if filter_grade_code:
            filter_values["grade"] = [filter_grade_code]

        if selected_subjects:
            filter_values["subject"] = [
                SUBJECTS[s] for s in selected_subjects if s in SUBJECTS
            ]

        # Handle Category Selection
        if category_code:
            # If 'assessments_book' is selected, include both 'external_book' and 'assessments_book'
            # to guarantee context coverage from both reference sources.
            if category_code == "assessments_book":
                filter_values["category"] = ["assessments_book", "external_book"]
            else:
                filter_values["category"] = [category_code]

        # --- RESOLVE PUBLISHERS ---
        target_publishers = []

        if user:
            user_grade = user.get("grade")
            user_publishers = user.get("preferred_publishers", {})

            if filter_grade_code and filter_grade_code == user_grade:
                if filter_values.get("subject"):
                    for subj_code in filter_values["subject"]:
                        pub = user_publishers.get(subj_code)
                        if pub:
                            target_publishers.append(pub)
                else:
                    target_publishers = list(user_publishers.values())
        else:
            if filter_grade_code:
                default_grade_pubs = DEFAULT_PUBLISHERS.get(filter_grade_code, {})
                if filter_values.get("subject"):
                    for subj_code in filter_values["subject"]:
                        pub = default_grade_pubs.get(subj_code)
                        if pub:
                            target_publishers.append(pub)
                else:
                    target_publishers = list(default_grade_pubs.values())

        if target_publishers:
            filter_values["book_publisher"] = list(set(target_publishers))

        # --- CONSTRUCT QDRANT FILTERS ---
        for key, values in filter_values.items():
            if not values:
                continue

            filters.append(
                FieldCondition(
                    key=key,
                    match=MatchAny(any=values),
                )
            )

        return Filter(must=filters) if filters else None

    def extract_requested_page(query: str):
        """
        Extracts page numbers mentioned in user queries across English and Arabic formats.
        Examples: 'صفحة 15', 'ص 12', 'page 45', 'p. 8'
        """
        patterns = [
            r'(?:صفحة|ص)\s*[:\.-]?\s*(\d+)',  # Arabic: صفحة 12 or ص 12
            r'(?:page|p\.)\s*[:\.-]?\s*(\d+)', # English: page 12 or p. 12
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None
    
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

        # Step 1: Upload files to Gemini Files API and extract metadata
        files_metadata = []
        if uploaded_files:
            with st.spinner("Uploading files..."):
                files_metadata = rag_service.upload_and_register_files(uploaded_files)

        # Step 2: Initialize chat if needed
        if user and not st.session_state.get("current_chat_id"):
            clear_cached_chats()
            st.session_state["current_chat_id"] = chat_service.create_chat()

        # Step 3: Save user message (with files metadata) to session state and render
        messages_data: list = st.session_state.get("messages_data", [])

        user_msg_dict = {
            "role": "user",
            "content": user_query,
            "files": files_metadata if files_metadata else None,
        }
        messages_data.append(user_msg_dict)

        # Save user msg timestamp
        user_timestamp = datetime.now().isoformat()

        # Render user attachments (if present) and message, then scroll down
        if files_metadata:
            render_file_attachments(files_metadata)
        render_user_prompt(user_query)
        scroll_to_bottom()

        # Step 4: Retrieve context and generate AI response
        try:
            with st.spinner("Generating..."):
                # Detect page numbers in prompt (Arabic/English)
                requested_page = extract_requested_page(user_query)

                full_lesson_source = (
                    bool(st.session_state.get("filter_grade"))
                    and bool(st.session_state.get("filter_subject"))
                    and len(st.session_state.get("filter_unit", [])) == 1
                    and bool(st.session_state.get("filter_lesson"))
                )

                if full_lesson_source:
                    # Full lesson drawer across Main Book & Assessment Book
                    sources_text = rag_service.scroll_from_filters(get_filters())

                elif requested_page is not None:
                    # Explicit page query: build a modified filter containing page_num
                    base_filter = get_filters()
                    page_condition = FieldCondition(
                        key="page_num",
                        match=MatchAny(any=[requested_page]),
                    )
                    
                    if base_filter:
                        base_filter.must.append(page_condition)
                        page_filter = base_filter
                    else:
                        page_filter = Filter(must=[page_condition])

                    sources_text = rag_service.scroll_from_filters(page_filter)

                else:
                    # Semantic search across filtered corpus
                    chunks_payloads = rag_service.search(
                        user_query,
                        limit=10,
                        score_threshold=0.5,
                        query_filter=get_filters(),
                    )

                    sources_text = rag_service.enrich_sources(chunks_payloads)

                # Get chat history for model context (excluding current query)
                chat_history = messages_data[:-1]

                # Build student info dict
                student_info = {}
                if user:
                    student_info = {"name": user["full_name"], "grade": user["grade"]}

                # --- Rendering the AI response (2 ways) ---
                is_first_prompt = len(chat_history) == 0

                if is_first_prompt:
                    # FIRST - get response, suggested chat title
                    json_response = rag_service.generate_response(
                        user_query,
                        sources_text,
                        files_metadata,
                        chat_history,
                        student_info,
                    )

                    full_response: str = json_response["response"]
                    sanitized_response = rag_service.sanitize_latex(full_response)
                    render_ai_response(sanitized_response)

                    # Update ss with full response
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": sanitized_response,
                        "is_error": False,
                    }
                    messages_data.append(assistant_msg_dict)

                    # Save to DB with file metadata
                    if user and st.session_state.get("current_chat_id"):
                        chat_service.save_message_and_title(
                            chat_id=st.session_state["current_chat_id"],
                            user_prompt=user_query,
                            user_timestamp=user_timestamp,
                            ai_response=sanitized_response,
                            title=json_response["suggested_chat_title"],
                            user_files=files_metadata if files_metadata else None,
                        )

                        clear_cached_chats()
                        st.session_state["sidebar_update_key"] += 1

                        # Overwrite the placeholder instantly
                        if is_creating_new_chat:
                            with chat_history_placeholder.container():
                                render_sidebar_chats()

                else:
                    # SECOND - stream response

                    # 1. Create a placeholder container for streaming
                    stream_container = st.empty()
                    accumulated_chunks = []

                    def stream_and_collect():
                        for chunk in rag_service.generate_response_stream(
                            user_query,
                            sources_text,
                            files_metadata,
                            chat_history,
                            student_info,
                        ):
                            accumulated_chunks.append(chunk)
                            yield chunk

                    # 2. Stream raw response to UI
                    with stream_container:
                        st.write_stream(stream_and_collect())

                    # 3. Combine chunks and sanitize full response once stream finishes
                    raw_accumulated = "".join(accumulated_chunks)
                    sanitized_response = rag_service.sanitize_latex(raw_accumulated)

                    # 4. Overwrite placeholder with clean LaTeX markdown
                    stream_container.markdown(sanitized_response)

                    # 5. Save sanitized response in session state
                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": sanitized_response,
                    }
                    messages_data.append(assistant_msg_dict)

                    # 6. Save sanitized response to database
                    if user and st.session_state.get("current_chat_id"):
                        chat_service.save_message(
                            chat_id=st.session_state["current_chat_id"],
                            user_prompt=user_query,
                            user_timestamp=user_timestamp,
                            ai_response=sanitized_response,
                            user_files=files_metadata if files_metadata else None,
                        )

        except Exception as e:
            messages_data.append(
                {
                    "role": "assistant",
                    "content": "",
                    "is_error": True,
                }
            )
            st.error(ERROR_MESSAGE)
            import traceback

            st.error(traceback.format_exc())

        # Update messages_data ss
        st.session_state["messages_data"] = messages_data

    elif not st.session_state.get("messages_data"):
        st.header("How can I help you today?", text_alignment="center", anchor=False)
