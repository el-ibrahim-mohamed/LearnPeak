import streamlit as st
import streamlit.components.v1 as components
import re
from streamlit_shortcuts import shortcut_button
from services.rag.chat_service import ChatService
from config import GRADES, SUBJECTS

# Set page config
st.set_page_config(
    page_title="Ask Your Book - LearnPeak",
    page_icon="static/mountain_logo.png",
    layout="centered",
    initial_sidebar_state="auto",
)


# Defining Functions
def get_key_by_value(d: dict, value):
    return next((k for k, v in d.items() if v == value), None)


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
        from services.rag.embedding_service import EmbeddingService
        from services.rag.qdrant_service import QdrantService
        from services.rag.rag_service import RagService, AddSource

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
            "country",
            "education",
            "book_publisher",
            "id",
            "grade",
            "subject",
        ]:
            qdrant_service.create_payload_index(
                qdrant_service.collection_name,
                payload_key,
                PayloadSchemaType.KEYWORD,
            )

        for payload_key in ["term", "unit_num", "lesson_num", "page_num"]:
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

    if st.session_state.get("user"):
        username = st.session_state["user"]["username"]

        @st.cache_data(ttl=3600)  # Caches for 1 hour
        def get_cached_chats(username):
            return chat_service.get_chats(username)

        chats = get_cached_chats(username)

        if chats:
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
                        key=f"chat_{chat['id']}",
                        use_container_width=True,
                    ):
                        # Load messages from Firebase
                        db_messages = chat_service.get_chat_messages(
                            username, chat["id"]
                        )

                        # Convert DB to UI format
                        formatted_messages = []
                        for m in db_messages:
                            if m["role"] == "user":
                                formatted_messages.append(
                                    {"role": "user", "msg": m.get("content", "")}
                                )
                            else:
                                formatted_messages.append(
                                    {
                                        "role": "assistant",
                                        "ai_response": m.get("content", ""),
                                    }
                                )

                        # 4. Save to session state
                        st.session_state["rag_page"] = "chat"
                        st.session_state["current_chat_id"] = chat["id"]
                        st.session_state["messages_data"] = formatted_messages

                # Rename chat button
                with col2:
                    with st.popover("", icon="✏️"):
                        new_chat_title = st.text_input(
                            "New chat name",
                            value=chat["title"],
                            icon="✍️",
                            label_visibility="collapsed",
                            key=f"rename_chat_{chat['id']}",
                        )

                        # Triggers auto-save on Enter or tap/click away
                        if new_chat_title.strip() and new_chat_title != chat["title"]:
                            chat_service.update_title(
                                username,
                                chat["id"],
                                new_chat_title.strip(),
                            )
                            st.cache_data.clear()
                            st.rerun()

                # Delete chat button
                with col3:
                    if st.button(
                        "", key=f"del_{chat['id']}", icon="🗑️", use_container_width=True
                    ):
                        chat_service.delete_chat(username, chat["id"])
                        st.cache_data.clear()
                        st.session_state["rag_page"] = "chat"
                        st.session_state["messages_data"] = []
                        st.session_state["current_chat_id"] = None
                        st.rerun()
        else:
            st.info("No chats found. Create your first one!")

# Determine the page to show (menu, chat)
page = st.session_state.get("rag_page", "menu")

# Menu page
if page == "menu":
    st.title("📚 Choose your subject", anchor=False)
    "---"

    # Custom CSS for the subjects buttons
    def button_container_html(btn_key):
        st.markdown(
            f"""
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
                margin: 0;
                line-height: 1.5;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

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

    if st.session_state.get("user"):
        " "
        user_grade_long = get_key_by_value(GRADES, st.session_state["user"]["grade"])

        st.subheader(user_grade_long, anchor=False)

        # Display subjects for user's grade
        subjects_list = list(SUBJECTS.keys())
        for i in range(0, len(subjects_list), 2):
            col1, col2 = st.columns(2)

            # First item in row
            subject = subjects_list[i]
            subj_code = SUBJECTS[subject]
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
                subj_code = SUBJECTS[subject]
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

    def right_align_user_msg():
        st.html("""
            <style>
                .stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {
                    display: flex;
                    flex-direction: row-reverse;
                    align-items: end;
                }

                [data-testid="stChatMessageAvatarUser"] + [data-testid="stChatMessageContent"] * {
                    text-align: left;
                }
            </style>
            """)

    def render_user_prompt(msg: dict):
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.write(msg["msg"])

    def render_messages(messages_data: list):

        # Custom HTML to right-align user messages
        right_align_user_msg()

        for msg in messages_data:
            msg: dict

            render_user_prompt(msg)

            if msg["role"] == "assistant":
                st.markdown(msg["ai_response"])

            " "
            " "

        # Scroll to bottom smoothly
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

                grade_options = ["♾️ All", *list(GRADES.keys())]
                grade_index = 0
                subject_options = ["♾️ All", *list(SUBJECTS.keys())]
                subject_index = 0

                if menu_choice != "all_grades":
                    selected_subject = menu_choice
                    subjects_codes = list(SUBJECTS.values())
                    try:
                        subject_index = subjects_codes.index(selected_subject) + 1
                    except Exception:
                        subject_index = 0

                    if st.session_state.get("user"):
                        try:
                            grade_index = grade_options.index(
                                get_key_by_value(
                                    GRADES, st.session_state["user"]["grade"]
                                )
                            )
                        except Exception:
                            grade_index = 0

                else:
                    if st.session_state.get("user"):
                        try:
                            grade_index = grade_options.index(
                                get_key_by_value(
                                    GRADES, st.session_state["user"]["grade"]
                                )
                            )
                        except Exception:
                            grade_index = 0

                grade_filter = st.selectbox("🎓 Grade", grade_options, grade_index)
                subject_filter = st.selectbox(
                    "📚 Subject", subject_options, subject_index
                )

                unit_num_filter = st.selectbox(
                    "📌 Unit",
                    ["♾️ All", 1, 2, 3, 4],
                    index=0,
                    accept_new_options=True,
                )
                lesson_num_filter = st.selectbox(
                    "📝 Lesson",
                    ["♾️ All", 1, 2, 3, 4],
                    index=0,
                    accept_new_options=True,
                )

        with col2:
            user_query = st.chat_input("Ask something...")

    def normalize_string(input_str: str):
        """
        1. Filter for alnum characters (removes emojis)
        2. Strip
        3. Replace spaces with underscores
        """
        return (
            "".join(char for char in input_str if char.isalnum() or char.isspace())
            .strip()
            .replace("  ", " ")
            .replace(" ", "_")
        )

    def get_filters():
        filters = []
        for key, value in {
            "grade": str(grade_filter),
            "subject": normalize_string(str(subject_filter)).lower(),
            "unit_num": normalize_string(str(unit_num_filter)),
            "lesson_num": normalize_string(str(lesson_num_filter)),
        }.items():
            if value and normalize_string(value).lower() != "all":
                if key in ["unit_num", "lesson_num"]:
                    value = int(value)
                elif key == "grade":
                    value = GRADES[value]

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
            st.cache_data.clear()

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

        assistant_msg_dict = {
            "role": "assistant",
            "ai_response": "",
            "is_ai_error": False,
        }
        messages_data.append(assistant_msg_dict)

        last_msg_idx = len(messages_data) - 1

        # Step 3: Save AI response and stream it
        with st.spinner("Generating..."):
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
                    )

                if username:
                    chat_service.update_title(
                        username,
                        st.session_state["current_chat_id"],
                        json_response["suggested_chat_title"],
                    )
                    st.cache_data.clear()

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
