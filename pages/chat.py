import streamlit as st
import re
from datetime import datetime
import unicodedata
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
        embedding_service = EmbeddingService()
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

# Initialize carried-over page context and turn counter
if "carried_over_pages" not in st.session_state:
    st.session_state["carried_over_pages"] = []
if "page_memory_turns_left" not in st.session_state:
    st.session_state["page_memory_turns_left"] = 0


def bound_get_textbook_page(
    page_num: int, grade: str, subject: str, category: str, book_publisher: str
):
    active_pages = st.session_state.get("carried_over_pages", [])

    current_grade = grade or st.session_state.get("filter_grade")
    current_subject = subject or SUBJECTS.get(st.session_state.get("filter_subject"))
    current_category = (
        category or st.session_state.get("filter_category_code") or "external_book"
    )

    current_publisher = book_publisher
    if not current_publisher and current_subject:
        if user and user.get("info", {}).get("preferred_book_publishers"):
            current_publisher = user["info"]["preferred_book_publishers"].get(
                current_subject
            )
        if not current_publisher:
            current_publisher = DEFAULT_PUBLISHERS.get(current_subject, "el-moasser")

    return rag_service.get_textbook_page(
        page_num=page_num,
        grade=current_grade,
        subject=current_subject,
        category=current_category,
        book_publisher=current_publisher,
        active_pages=active_pages,
    )


@st.cache_data(ttl=3600, show_spinner=False)
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
                        key=f"chat_{chat['id']}_{counter}",
                        use_container_width=True,
                    ):
                        db_chat_messages = chat_service.get_chat_messages(chat["id"])

                        st.session_state["rag_page"] = "chat"
                        st.session_state["current_chat_id"] = chat["id"]
                        st.session_state["messages_data"] = db_chat_messages
                        st.session_state["scroll_to_bottom"] = True
                        st.rerun()

                with col2:
                    with st.popover("", icon="✏️"):
                        new_chat_title = st.text_input(
                            "New chat name",
                            value=chat["title"],
                            icon="✍️",
                            label_visibility="collapsed",
                            key=f"rename_chat_{chat['id']}_{counter}",
                        )

                        if new_chat_title.strip() and new_chat_title != chat["title"]:
                            chat_service.update_title(
                                chat["id"],
                                new_chat_title.strip(),
                            )
                            clear_cached_chats()
                            st.rerun(scope="fragment")

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
    if st.button("Menu", icon="📋", use_container_width=True):
        st.session_state["rag_page"] = "menu"
        st.session_state["messages_data"] = []
        st.session_state["current_chat_id"] = None
        st.switch_page("pages/chat_menu.py")

    from streamlit_shortcuts import shortcut_button

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
        st.rerun()

    st.caption("Your chats")

    current_chat_input = st.session_state.get("main_chat_input")
    is_creating_new_chat = bool(current_chat_input) and not st.session_state.get(
        "current_chat_id"
    )

    chat_history_placeholder = st.empty()
    if is_creating_new_chat:
        with chat_history_placeholder.container():
            render_sidebar_chats()
    else:
        render_sidebar_chats()


# Chat page logic
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
    if not files_list:
        return

    icon_map = {"pdf": "📄", "image": "🖼️", "code": "💻", "document": "📝"}

    cols = st.columns(min(len(files_list), 4))
    for idx, file_data in enumerate(files_list):
        category = file_data.get("file_type_category", "document")
        icon = icon_map.get(category, "📎")
        file_name = file_data.get("file_name", "Attachment")

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


def normalize_arabic_digits(text: str) -> str:
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    ascii_digits = "0123456789"
    translation_table = str.maketrans(arabic_digits, ascii_digits)
    return text.translate(translation_table)


def normalize_text(text: str) -> str:
    text = normalize_arabic_digits(text.lower())
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ى", "ي", text)
    return text


def extract_requested_pages(query: str) -> list[int]:
    if not query:
        return []

    norm_query = normalize_text(query)
    found_pages = set()

    PREFIX = r"(?:\b(?:pages?|pgs?\.?|صفحة|الصفحة|صفحات|الصفحات)\b|\b(?:p|pg|ص)\b\.?|(?:\b(?:p|pg|ص)\.?)(?=\d))"

    range_pattern = (
        r"(?:من\s+)?"
        + PREFIX
        + r"\s*[:\.-]*\s*(\d+)\s*(?:-|to|through|الي|حتي|وحتي)\s*(?:"
        + PREFIX
        + r"\s*[:\.-]*\s*)?(\d+)"
    )
    for match in re.finditer(range_pattern, norm_query):
        start, end = int(match.group(1)), int(match.group(2))
        if 1 <= start <= 1000 and 1 <= end <= 1000:
            if start <= end and (end - start) <= 30:
                found_pages.update(range(start, end + 1))
            elif start > end and (start - end) <= 30:
                found_pages.update(range(end, start + 1))

    list_pattern = (
        PREFIX
        + r"\s*[:\.-]*\s*(\d+(?:\s*(?:[,،&]|and|و)\s*(?:"
        + PREFIX
        + r"\s*)?\d+)+)"
    )
    for match in re.finditer(list_pattern, norm_query):
        numbers = re.findall(r"\d+", match.group(1))
        for num in numbers:
            val = int(num)
            if 1 <= val <= 1000:
                found_pages.add(val)

    single_pattern = PREFIX + r"\s*[:\.-]*\s*(\d+)"
    for match in re.finditer(single_pattern, norm_query):
        val = int(match.group(1))
        if 1 <= val <= 1000:
            found_pages.add(val)

    sorted_pages = sorted(list(found_pages))
    return sorted_pages[:15]


@st.fragment
def render_filter_popover():
    with st.popover("", icon="➕", help="Apply filters to get better results"):
        menu_choice = st.session_state.get("menu_choice", "all_grades")

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

        grade_filter = (
            GRADES[selected_grade_label] if selected_grade_label != "All" else None
        )

        st.session_state["filter_grade"] = grade_filter

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

        subject_options = ["All"] + list(available_subjects_dict.keys())

        default_subject_index = 0
        if menu_choice != "all_grades":
            chosen_subject_label = get_key_by_value(SUBJECTS, menu_choice)
            if chosen_subject_label and chosen_subject_label in available_subjects_dict:
                default_subject_index = subject_options.index(chosen_subject_label)

        selected_subject = st.selectbox(
            "📚 Subject",
            options=subject_options,
            index=default_subject_index,
            key="filter_subject_select",
        )

        st.session_state["filter_subject"] = (
            selected_subject if selected_subject != "All" else None
        )

        is_english_selected = selected_subject and (
            selected_subject.lower() == "english"
            or SUBJECTS.get(selected_subject) == "english"
        )

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

        selected_units = st.multiselect(
            "📌 Unit",
            options=UNIT_OPTIONS,
            key="filter_unit_raw",
            accept_new_options=True,
        )

        valid_units = [u for u in selected_units if str(u).isdigit()]
        if len(valid_units) != len(selected_units):
            st.caption("⚠️ Only numbers are allowed for Units.")
        st.session_state["filter_unit"] = valid_units

        selected_lessons = st.multiselect(
            "📝 Lesson",
            options=LESSON_OPTIONS,
            key="filter_lesson_raw",
            accept_new_options=True,
        )

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


def get_filters(
    include_unit_lesson: bool = True,
    strict_category: bool = False,
    unit_num_override: list = None,
    lesson_num_override: list = None,
) -> Filter:
    filter_conditions = []

    grade_code = st.session_state.get("filter_grade")
    subject_label = st.session_state.get("filter_subject")
    category_code = st.session_state.get("filter_category_code")

    unit_num = (
        unit_num_override
        if unit_num_override is not None
        else st.session_state.get("filter_unit")
    )
    lesson_num = (
        lesson_num_override
        if lesson_num_override is not None
        else st.session_state.get("filter_lesson")
    )

    if grade_code:
        filter_conditions.append(
            FieldCondition(key="grade", match=MatchAny(any=[grade_code]))
        )

    if subject_label and subject_label in SUBJECTS:
        subj_code = SUBJECTS[subject_label]
        filter_conditions.append(
            FieldCondition(key="subject", match=MatchAny(any=[subj_code]))
        )

        target_publisher = None
        if user and user.get("info", {}).get("preferred_book_publishers"):
            target_publisher = user["info"]["preferred_book_publishers"].get(subj_code)
        if not target_publisher:
            target_publisher = DEFAULT_PUBLISHERS.get(subj_code)

        if target_publisher:
            if category_code == "assessments_book":
                if strict_category:
                    filter_conditions.append(
                        FieldCondition(
                            key="book_publisher",
                            match=MatchAny(any=["moe"]),
                        )
                    )
                else:
                    filter_conditions.append(
                        FieldCondition(
                            key="book_publisher",
                            match=MatchAny(any=list(set(["moe", target_publisher]))),
                        )
                    )
            else:
                filter_conditions.append(
                    FieldCondition(
                        key="book_publisher", match=MatchAny(any=[target_publisher])
                    )
                )

    if category_code:
        if category_code == "assessments_book":
            if strict_category:
                filter_conditions.append(
                    FieldCondition(
                        key="category", match=MatchAny(any=["assessments_book"])
                    )
                )
            else:
                filter_conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchAny(any=["assessments_book", "external_book"]),
                    )
                )
        else:
            filter_conditions.append(
                FieldCondition(key="category", match=MatchAny(any=[category_code]))
            )

    if include_unit_lesson:
        if unit_num:
            filter_conditions.append(
                FieldCondition(key="unit_num", match=MatchAny(any=unit_num))
            )
        if lesson_num:
            filter_conditions.append(
                FieldCondition(key="lesson_num", match=MatchAny(any=lesson_num))
            )

    return Filter(must=filter_conditions)


render_messages(st.session_state.get("messages_data", []))

if st.session_state.get("scroll_to_bottom"):
    scroll_to_bottom()
    st.session_state["scroll_to_bottom"] = False

if user_input:
    user_query = user_input.text
    uploaded_files = user_input.files

    files_metadata = []
    if uploaded_files:
        with st.spinner("Uploading files..."):
            files_metadata = rag_service.upload_and_register_files(uploaded_files)

    if user and not st.session_state.get("current_chat_id"):
        clear_cached_chats()
        st.session_state["current_chat_id"] = chat_service.create_chat()

    messages_data: list = st.session_state.get("messages_data", [])

    user_msg_dict = {
        "role": "user",
        "content": user_query,
        "files": files_metadata if files_metadata else None,
    }
    messages_data.append(user_msg_dict)

    user_timestamp = datetime.now().isoformat()

    if files_metadata:
        render_file_attachments(files_metadata)

    render_user_prompt(user_query)
    scroll_to_bottom()

    try:
        with st.spinner("Generating..."):
            current_requested_pages = extract_requested_pages(user_query)

            # --- Persistent Carry-Over Logic (2 turns) ---
            if current_requested_pages:
                st.session_state["carried_over_pages"] = list(
                    set(
                        st.session_state.get("carried_over_pages", [])
                        + current_requested_pages
                    )
                )
                st.session_state["page_memory_turns_left"] = 2

            requested_pages = st.session_state.get("carried_over_pages", [])

            if st.session_state.get("page_memory_turns_left", 0) > 0:
                st.session_state["page_memory_turns_left"] -= 1
                if st.session_state["page_memory_turns_left"] == 0:
                    st.session_state["carried_over_pages"] = []

            extracted_page_chunks = []
            if requested_pages:
                page_filters = []

                filter_grade_code = st.session_state.get("filter_grade")
                selected_subject_label = st.session_state.get("filter_subject")
                category_code = st.session_state.get("filter_category_code")

                if filter_grade_code:
                    page_filters.append(
                        FieldCondition(
                            key="grade", match=MatchAny(any=[filter_grade_code])
                        )
                    )

                if selected_subject_label and selected_subject_label in SUBJECTS:
                    subj_code = SUBJECTS[selected_subject_label]
                    page_filters.append(
                        FieldCondition(key="subject", match=MatchAny(any=[subj_code]))
                    )

                    target_publisher = None
                    if user and user.get("info", {}).get("preferred_book_publishers"):
                        target_publisher = user["info"][
                            "preferred_book_publishers"
                        ].get(subj_code)
                    if not target_publisher:
                        target_publisher = DEFAULT_PUBLISHERS.get(subj_code)

                    if target_publisher:
                        if category_code == "assessments_book":
                            page_filters.append(
                                FieldCondition(
                                    key="book_publisher",
                                    match=MatchAny(
                                        any=list(set(["moe", target_publisher]))
                                    ),
                                )
                            )
                        else:
                            page_filters.append(
                                FieldCondition(
                                    key="book_publisher",
                                    match=MatchAny(any=[target_publisher]),
                                )
                            )

                if category_code:
                    if category_code == "assessments_book":
                        page_filters.append(
                            FieldCondition(
                                key="category", match=MatchAny(any=["assessments_book"])
                            )
                        )
                    else:
                        page_filters.append(
                            FieldCondition(
                                key="category", match=MatchAny(any=[category_code])
                            )
                        )

                page_filters.append(
                    FieldCondition(key="page_num", match=MatchAny(any=requested_pages))
                )

                page_filter = Filter(must=page_filters)
                extracted_page_chunks = rag_service.scroll(page_filter)

            auto_extracted_units = set()
            auto_extracted_lessons = set()

            for chunk in extracted_page_chunks:
                u_num = chunk.get("unit_num")
                l_num = chunk.get("lesson_num")

                if u_num is not None:
                    if isinstance(u_num, (list, tuple)):
                        auto_extracted_units.update(u_num)
                    else:
                        auto_extracted_units.add(u_num)

                if l_num is not None:
                    if isinstance(l_num, (list, tuple)):
                        auto_extracted_lessons.update(l_num)
                    else:
                        auto_extracted_lessons.add(l_num)

            manual_units = st.session_state.get("filter_unit") or []
            manual_lessons = st.session_state.get("filter_lesson") or []

            effective_units = (
                manual_units if manual_units else list(auto_extracted_units)
            )
            effective_lessons = (
                manual_lessons if manual_lessons else list(auto_extracted_lessons)
            )

            user_selected_full_lesson = bool(manual_units) and bool(manual_lessons)

            search_filters = get_filters(
                unit_num_override=effective_units, lesson_num_override=effective_lessons
            )

            if user_selected_full_lesson:
                primary_chunks = rag_service.scroll(search_filters)
            else:
                recent_user_queries = [
                    msg.get("content", "").strip()
                    for msg in messages_data
                    if msg.get("role") == "user" and msg.get("content", "").strip()
                ][-2:]
                semantic_search_query = "\n".join(recent_user_queries)

                primary_chunks = rag_service.search(
                    semantic_search_query,
                    limit=10,
                    score_threshold=0.5,
                    query_filter=search_filters,
                )

            combined_chunks = extracted_page_chunks + primary_chunks
            deduped_chunks = rag_service.deduplicate_chunks(combined_chunks)

            if deduped_chunks:
                sources_text = rag_service.enrich_sources(
                    deduped_chunks, priority_pages=requested_pages
                )
            else:
                sources_text = ""

            chat_history = messages_data[:-1]

            student_info = {}
            if user:
                student_info = {"name": user["full_name"], "grade": user["grade"]}

            active_filters = {
                "grade": st.session_state.get("filter_grade"),
                "subject": st.session_state.get("filter_subject"),
                "category": st.session_state.get("filter_category_code"),
                "unit": st.session_state.get("filter_unit"),
                "lesson": st.session_state.get("filter_lesson"),
            }

            is_first_prompt = len(chat_history) == 0

            if is_first_prompt:
                json_response = rag_service.generate_response(
                    user_query,
                    sources_text,
                    files_metadata,
                    chat_history,
                    student_info,
                    active_filters,
                    tools=[bound_get_textbook_page],
                )

                full_response: str = rf"{json_response['response']}"
                sanitized_response = full_response
                render_ai_response(sanitized_response)

                assistant_msg_dict = {
                    "role": "assistant",
                    "content": sanitized_response,
                    "is_error": False,
                }
                messages_data.append(assistant_msg_dict)

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

                    if is_creating_new_chat:
                        with chat_history_placeholder.container():
                            render_sidebar_chats()

            else:
                stream_container = st.empty()
                accumulated_chunks = []

                def stream_and_collect():
                    for chunk in rag_service.generate_response_stream(
                        user_query,
                        sources_text,
                        files_metadata,
                        chat_history,
                        student_info,
                        active_filters,
                        tools=[bound_get_textbook_page]
                    ):
                        accumulated_chunks.append(chunk)
                        yield chunk

                with stream_container:
                    st.write_stream(stream_and_collect())

                raw_accumulated = rf"{''.join(accumulated_chunks)}"
                sanitized_response = raw_accumulated

                stream_container.markdown(sanitized_response)

                assistant_msg_dict = {
                    "role": "assistant",
                    "content": sanitized_response,
                }
                messages_data.append(assistant_msg_dict)

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

    st.session_state["messages_data"] = messages_data

elif not st.session_state.get("messages_data"):
    st.header("How can I help you today?", text_alignment="center", anchor=False)