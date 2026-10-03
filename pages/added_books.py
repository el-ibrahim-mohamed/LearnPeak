import streamlit as st
from datetime import datetime
import pandas as pd
from config import *
from services.rag.qdrant_service import QdrantService

st.set_page_config(
    page_title="Added Books - LearnPeak",
    page_icon="📚",
    layout="centered",
)


# Initialize Qdrant service using cached resource
@st.cache_resource
def get_qdrant_service():
    return QdrantService(
        url=st.secrets["qdrant"]["URL"],
        api_key=st.secrets["qdrant"]["API_KEY"],
        vector_size=EMBEDDING_VECTOR_SIZE,
    )


# Cache book list retrieval from Qdrant vector DB
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_added_books():
    qdrant = get_qdrant_service()
    unique_books = set()
    offset = None

    while True:
        records, offset = qdrant.scroll(
            collection_name=qdrant.collection_name,
            with_payload=["grade", "subject", "book_publisher", "category"],
            limit=100,
            offset=offset,
        )

        for record in records:
            payload = record.payload or {}
            grade = payload.get("grade", "Unknown")
            publisher = payload.get("book_publisher", "Unknown")
            subject = payload.get("subject", "Unknown")
            category = payload.get("category", "")

            unique_books.add((grade, publisher, subject, category))

        if offset is None:
            break

    data = []
    for grade_code, pub_code, subj_code, category in sorted(unique_books):
        grade_name = get_key_by_value(GRADES, grade_code) or grade_code
        pub_name = get_key_by_value(BOOK_PUBLISHERS, pub_code) or pub_code
        subj_name = get_key_by_value(SUBJECTS, subj_code) or subj_code

        data.append(
            {
                "Grade Code": grade_code,
                "Grade": grade_name,
                "Subject Code": subj_code,
                "Subject": subj_name,
                "Publisher": pub_name,
                "Category": category if category else "Main",
            }
        )

    return pd.DataFrame(data)


# Header
st.title("📚 Added Books Library")
st.caption(
    "Explore all curriculum textbooks currently indexed and available in LearnPeak."
)

# Fetch books
with st.spinner("Fetching indexed books library..."):
    books_df = fetch_added_books()

# Action Row (Search / Refresher)
col_search, col_ref = st.columns([4, 1])
with col_ref:
    if st.button(
        "🔄 Refresh", use_container_width=True, help="Force refresh book list"
    ):
        st.cache_data.clear()
        st.rerun()

# Filtering Section
if not books_df.empty:
    col1, col2 = st.columns(2)
    with col1:
        grade_options = ["All Grades"] + sorted(list(books_df["Grade"].unique()))
        selected_grade = st.selectbox("Filter by Grade", grade_options)
    with col2:
        subject_options = ["All Subjects"] + sorted(list(books_df["Subject"].unique()))
        selected_subject = st.selectbox("Filter by Subject", subject_options)

    # Apply filters
    filtered_df = books_df.copy()
    if selected_grade != "All Grades":
        filtered_df = filtered_df[filtered_df["Grade"] == selected_grade]
    if selected_subject != "All Subjects":
        filtered_df = filtered_df[filtered_df["Subject"] == selected_subject]

    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Indexed Books", len(filtered_df))
    m2.metric("Grades Covered", filtered_df["Grade"].nunique())
    m3.metric("Subjects Covered", filtered_df["Subject"].nunique())

    # Table Display
    st.markdown("### 📋 Available Textbooks")
    st.dataframe(
        filtered_df[["Grade", "Subject", "Publisher", "Category"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No textbooks have been indexed in the database yet.")

st.divider()

# =========================================================
# REQUEST A NEW BOOK FORM
# =========================================================

# Place HTML anchor tag right before the header
st.subheader("📚 Can't find your exact textbook?")
st.write(
    "Request a new book to be processed and added to LearnPeak. We will review and index it into the platform ASAP."
)


@st.fragment
def request_book_form():
    with st.container(border=True):
        # Row 1: Grade and Subject
        col1, col2 = st.columns(2)
        with col1:
            req_grade = st.selectbox("Grade", list(GRADES.keys()), key="req_grade")
        with col2:
            # Dynamically filter subjects based on grade if available
            selected_grade_code = GRADES.get(req_grade)
            available_subjects = (
                get_subjects_for_grade(selected_grade_code)
                if selected_grade_code
                else SUBJECTS
            )
            req_subject = st.selectbox(
                "Subject", list(available_subjects.keys()), key="req_subj"
            )

        # Row 2: Category and Publisher (Slicing based on Category)
        col1, col2 = st.columns(2)
        with col1:
            if isinstance(req_subject, str) and "english" in req_subject.lower():
                req_category_label = st.selectbox(
                    "English Book Category",
                    list(ENGLISH_CATEGORIES.keys()),
                    key="req_english_cat",
                )
                req_category = ENGLISH_CATEGORIES[req_category_label]
            else:
                req_category_label = st.selectbox(
                    "Book Category",
                    list(CATEGORIES.keys()),
                    key="req_general_cat",
                )
                req_category = CATEGORIES[req_category_label]

        with col2:
            is_assessments_book = req_category == "assessments_book"

            book_publishers = list(BOOK_PUBLISHERS.keys())
            if is_assessments_book:
                book_publishers = [book_publishers[0]]
            else:
                book_publishers = book_publishers[1:]

            req_publisher = st.selectbox(
                "Book Publisher",
                book_publishers,
                key="req_publisher_select",
            )

        # Row 3: Notes (Alone)
        req_notes = st.text_input(
            "Notes (Optional)",
            placeholder="Attach any notes...",
            key="req_notes_input",
        )

        submit_req = st.button(
            "📩 Send Book Request", type="primary", use_container_width=True
        )

        if submit_req:
            user_info = st.session_state.get("user", {})
            request_data = {
                "grade": GRADES.get(req_grade),
                "subject": SUBJECTS.get(req_subject),
                "category": req_category,
                "publisher": BOOK_PUBLISHERS.get(req_publisher),
                "notes": req_notes.strip(),
                "requested_at": datetime.now().isoformat(),
                "user_uid": user_info.get("uid", "anonymous"),
                "user_name": user_info.get("full_name", "Guest"),
                "status": "pending",
            }

            try:
                root_ref = st.session_state["root_ref"]
                root_ref.child("support/book_additions").push(request_data)
                st.success(
                    "🎉 Thank you! Your book request has been submitted successfully."
                )
            except Exception as e:
                st.error(f"Failed to send request: {str(e)}")


request_book_form()
