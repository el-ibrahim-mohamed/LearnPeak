import streamlit as st
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
        from qdrant_client.models import PayloadSchemaType
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
                        st.switch_page("pages/chat.py")

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
                        st.switch_page("pages/chat.py")

        else:
            st.info("No chats found. Create your first one!")

    else:
        st.info("Sign in to save your chats.")


with st.sidebar:
    if st.button("Menu", icon="📋", use_container_width=True):
        st.session_state["rag_page"] = "menu"
        st.session_state["messages_data"] = []
        st.session_state["current_chat_id"] = None
        st.rerun()

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
        st.switch_page("pages/chat.py")

    st.caption("Your chats")

    current_chat_input = st.session_state.get("main_chat_input")
    is_creating_new_chat = bool(current_chat_input) and not st.session_state.get(
        "current_chat_id"
    )

    if is_creating_new_chat:
        chat_history_placeholder = st.empty()
        with chat_history_placeholder.container():
            render_sidebar_chats()
    else:
        render_sidebar_chats()


# Menu page content
st.title("📚 Choose your subject", anchor=False)

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


def button_container_html(btn_key):
    st.html(f"""
        <style>
        .st-key-{btn_key} button {{
            height: auto;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid rgba(128, 128, 128, 0.2); 
            text-align: center;
            display: block;
            transition: all 0.3s ease-in-out;
            white-space: pre-wrap;
        }}

        .st-key-{btn_key} button:hover {{
            border-color: var(--primary-color);
            filter: brightness(0.95);
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


if user:
    user_grade_code = user.get("grade", "prim4")
    user_grade_long = get_key_by_value(GRADES, user_grade_code) or "Your Grade"

    st.subheader(user_grade_long, anchor=False)

    grade_subjects_dict = get_subjects_for_grade(user_grade_code)
    subjects_list = list(grade_subjects_dict.keys())

    for i in range(0, len(subjects_list), 2):
        col1, col2 = st.columns(2)

        subject = subjects_list[i]
        subj_code = grade_subjects_dict[subject]
        btn_key = f"subject_{subj_code}"

        with col1:
            button_container_html(btn_key)
            if st.button(subject, use_container_width=True, key=btn_key):
                st.session_state["menu_choice"] = subj_code
                st.session_state["filter_grade"] = user_grade_code
                st.session_state["filter_grade_select"] = user_grade_long
                st.session_state["filter_subject_select"] = subject
                st.session_state["rag_page"] = "chat"
                st.session_state["messages_data"] = []
                st.session_state["current_chat_id"] = None
                st.switch_page("pages/chat.py")

        if i + 1 < len(subjects_list):
            subject = subjects_list[i + 1]
            subj_code = grade_subjects_dict[subject]
            btn_key = f"subject_{subj_code}"

            with col2:
                button_container_html(btn_key)
                if st.button(subject, use_container_width=True, key=btn_key):
                    st.session_state["menu_choice"] = subj_code
                    st.session_state["filter_grade"] = user_grade_code
                    st.session_state["filter_grade_select"] = user_grade_long
                    st.session_state["filter_subject_select"] = subject
                    st.session_state["rag_page"] = "chat"
                    st.session_state["messages_data"] = []
                    st.session_state["current_chat_id"] = None
                    st.switch_page("pages/chat.py")
else:
    # Guest view: show all grades sorted from prep3 to prim1, with subject buttons under each
    grade_order = [
        "prep3", "prep2", "prep1",
        "prim6", "prim5", "prim4", "prim3", "prim2", "prim1"
    ]

    for g_code in grade_order:
        g_label = get_key_by_value(GRADES, g_code)
        if not g_label:
            continue

        st.subheader(g_label, anchor=False)
        grade_subjects_dict = get_subjects_for_grade(g_code)
        subjects_list = list(grade_subjects_dict.keys())

        for i in range(0, len(subjects_list), 2):
            col1, col2 = st.columns(2)

            subject = subjects_list[i]
            subj_code = grade_subjects_dict[subject]
            btn_key = f"guest_subject_{g_code}_{subj_code}"

            with col1:
                button_container_html(btn_key)
                if st.button(subject, use_container_width=True, key=btn_key):
                    st.session_state["menu_choice"] = subj_code
                    st.session_state["filter_grade"] = g_code
                    st.session_state["filter_grade_select"] = g_label
                    st.session_state["filter_subject_select"] = subject
                    st.session_state["rag_page"] = "chat"
                    st.session_state["messages_data"] = []
                    st.session_state["current_chat_id"] = None
                    st.switch_page("pages/chat.py")

            if i + 1 < len(subjects_list):
                subject = subjects_list[i + 1]
                subj_code = grade_subjects_dict[subject]
                btn_key = f"guest_subject_{g_code}_{subj_code}"

                with col2:
                    button_container_html(btn_key)
                    if st.button(subject, use_container_width=True, key=btn_key):
                        st.session_state["menu_choice"] = subj_code
                        st.session_state["filter_grade"] = g_code
                        st.session_state["filter_grade_select"] = g_label
                        st.session_state["filter_subject_select"] = subject
                        st.session_state["rag_page"] = "chat"
                        st.session_state["messages_data"] = []
                        st.session_state["current_chat_id"] = None
                        st.switch_page("pages/chat.py")

        " "

    "---"
    st.space()
    st.info("Sign in to save your chats and personalize your experience.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "Sign In",
            icon="🔐",
            use_container_width=True,
            key="guest_signin_btn",
        ):
            st.switch_page("pages/signin.py")
    with col2:
        if st.button(
            "Create Account",
            type="primary",
            icon="👤",
            use_container_width=True,
            key="guest_signup_btn",
        ):
            st.switch_page("pages/signin.py")