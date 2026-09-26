from datetime import datetime
from io import BytesIO
import json
import re
import os
import time
from typing import Literal, Optional
import uuid
from pydantic import BaseModel, Field
import zipfile

import pymupdf
from google import genai
from google.genai import types
from mistralai.client import Mistral
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
)

from services.rag.embedding_service import EmbeddingService
from services.rag.qdrant_service import QdrantService
from config import *


class RagService:
    """
    Business logic layer for handling Q&A vector storage and retrieval.
    """

    def __init__(
        self,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        gemini_client: genai.Client,
    ):
        self.qdrant_service = qdrant_service
        self.collection_name = qdrant_service.collection_name
        self.embedding_service = embedding_service
        self.gemini_client = gemini_client

    # -------------------------
    # Insert Methods
    # -------------------------

    def insert_batch(
        self,
        chunks: list[dict],
    ) -> None:
        """
        Embed and insert a batch of chunks into the Qdrant collection.
        """

        if not chunks:
            return

        # Batch embedding (single model call)
        embeddings = self.embedding_service.embed(
            texts=[chunk["chunk_text"] for chunk in chunks],
            task="passage",
        )

        points = [
            PointStruct(
                id=chunk["id"],
                vector=embedding,
                payload=chunk,
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        self.qdrant_service.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    # -------------------------
    # Search Methods
    # -------------------------

    def search(
        self,
        user_question: str,
        limit: int = 10,
        score_threshold: float = 0.8,
        query_filter: Optional[Filter] = None,
    ) -> list[dict]:
        """
        Takes raw user question string, encodes internally, returns list of payload dicts.
        """

        query_embedding = self.embedding_service.embed([user_question], "query")[0]

        response = self.qdrant_service.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

        results = response.points

        return [res.payload for res in results] if results else []

    def scroll(self, scroll_filter: Filter):
        all_points = []
        offset = None

        while True:

            points, offset = self.qdrant_service.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                limit=100,
                offset=offset,
            )

            all_points.extend(points)

            if offset is None:
                break

        return [p.payload for p in all_points]

    # -------------------------
    # Collect Sources Methods
    # -------------------------

    def enrich_sources(self, chunks_payloads: list[dict]) -> str:
        """
        Enriches retrieved chunks by fetching all chunks belonging strictly to
        the exact pages, grades, and subjects of the retrieved results.
        """
        if not chunks_payloads:
            return ""

        # Build filter groups specific to individual pages within specific books
        should_filters = []
        for payload in chunks_payloads:
            must_conditions = []

            # Precise identity keys to isolate pages to their exact grade/book
            identity_keys = [
                "country",
                "education",
                "grade",
                "term",
                "subject",
                "book_publisher",
                "unit_num",
                "page_num",
            ]

            for key in identity_keys:
                if payload.get(key) is not None:
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=payload[key]))
                    )

            if must_conditions:
                should_filters.append(Filter(must=must_conditions))

        if not should_filters:
            return ""

        filters = Filter(should=should_filters)

        # Retrieve all chunks belonging strictly to these specific target pages
        chunks_results = self.scroll(filters)

        # Sort chunks strictly by textbook order
        chunks_results.sort(
            key=lambda chunk: (
                chunk.get("grade", ""),
                chunk.get("subject", ""),
                chunk.get("unit_num") or 0,
                (
                    min(chunk["lesson_num"])
                    if chunk.get("lesson_num")
                    and isinstance(chunk.get("lesson_num"), (list, tuple))
                    else (chunk.get("lesson_num") or 0)
                ),
                chunk.get("page_num") or 0,
                chunk.get("chunk_order") or 0,
            )
        )

        sources_text = ""
        current_page = None

        for chunk in chunks_results:
            page = (
                chunk.get("grade"),
                chunk.get("subject"),
                chunk.get("unit_num"),
                (
                    tuple(chunk["lesson_num"])
                    if isinstance(chunk.get("lesson_num"), list)
                    else chunk.get("lesson_num")
                ),
                chunk.get("page_num"),
            )

            if page != current_page:
                if current_page is not None:
                    sources_text += "\n\n" + "-" * 50 + "\n\n"

                sources_text += (
                    f'=== Grade: {chunk.get("grade", "N/A")} | '
                    f'Subject: {chunk.get("subject", "")} | '
                    f'Unit {chunk.get("unit_num", "N/A")} | '
                    f'Lesson {chunk.get("lesson_num", "N/A")} | '
                    f'Page {chunk.get("page_num", "N/A")} ===\n\n'
                )

                current_page = page

            sources_text += chunk.get("chunk_text", "") + "\n"

        return sources_text.strip()

    def scroll_from_filters(
        self,
        filters: Filter,
    ) -> str:
        """
        Retrieve all textbook chunks matching the selected curriculum filters.

        Unlike semantic search, this retrieves every matching chunk from Qdrant,
        allowing the quiz generator to use an entire book, unit, or lesson.
        """

        chunks = self.scroll(filters)

        if not chunks:
            return ""

        # Sort everything into textbook order.
        chunks.sort(
            key=lambda chunk: (
                chunk.get("unit_num", 0),
                (
                    min(chunk["lesson_num"])
                    if isinstance(chunk["lesson_num"], list)
                    else chunk["lesson_num"]
                ),
                chunk.get("page_num", 0),
                chunk.get("chunk_order", 0),
            )
        )

        sources_text = ""
        current_page = None

        for chunk in chunks:
            page = (
                chunk.get("book_publisher", ""),
                chunk.get("unit_num"),
                chunk.get("lesson_num"),
                chunk.get("page_num"),
            )

            if page != current_page:
                if current_page is not None:
                    sources_text += "\n\n" + "-" * 50 + "\n\n"

                sources_text += (
                    f'=== {get_key_by_value(SUBJECTS, chunk.get("subject"))} | '
                    f'Unit {chunk["unit_num"]} | '
                    f'Lesson {chunk["lesson_num"]} | '
                    f'Page {chunk["page_num"]} ===\n\n'
                )

                current_page = page

            sources_text += chunk["chunk_text"] + "\n"

        return sources_text.strip()

    # -------------------------
    # AI Mode Methods
    # -------------------------

    def upload_and_register_files(
        self,
        uploaded_files: list,
    ) -> list[dict]:
        """
        Uploads new files to Gemini Files API and returns their metadata list
        including file category, mime type, and Gemini file reference name.
        """
        file_metadata_list = []

        if not uploaded_files:
            return file_metadata_list

        for file in uploaded_files:
            file_bytes = file.getvalue()
            mime_type = file.type or "application/octet-stream"
            file_name = file.name

            # Categorize file for UI icon rendering
            if mime_type.startswith("image/"):
                category = "image"
            elif mime_type == "application/pdf":
                category = "pdf"
            elif "code" in mime_type or file_name.endswith(
                (".py", ".js", ".html", ".css", ".json", ".csv")
            ):
                category = "code"
            else:
                category = "document"

            try:
                uploaded_doc = self.gemini_client.files.upload(
                    file=BytesIO(file_bytes),
                    config=types.UploadFileConfig(
                        mime_type=mime_type,
                        display_name=file_name,
                    ),
                )

                file_info = {
                    "file_name": file_name,
                    "mime_type": mime_type,
                    "file_type_category": category,
                    "gemini_file_uri": uploaded_doc.uri,
                    "gemini_file_name": uploaded_doc.name,
                }

                file_metadata_list.append(file_info)

            except Exception as e:
                print(f"Failed to upload {file_name} to Gemini Files API: {e}")

        return file_metadata_list

    def generate_response(
        self,
        user_query,
        sources: str,
        uploaded_files: list = [],
        chat_history: list = [],
        student_info: dict = {},
    ):
        contents, system_instructions = self.ai_instructions(
            user_query,
            sources,
            uploaded_files,
            chat_history,
            student_info,
            output_format="json",
        )

        # Create the response json schema
        class AIResponseSchema(BaseModel):
            response: str = Field(description="Your full Markdown-formatted answer")
            suggested_chat_title: str = Field(
                description="A short, concise 2-5 word title summarizing the user query"
            )

        response = None

        for model in [
            GEMINI_MODELS_CODES["3.5-flash-lite"],
            GEMINI_MODELS_CODES["2.5-flash-lite"],
            GEMINI_MODELS_CODES["3.6-flash"],
        ]:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instructions,
                        max_output_tokens=40000,
                        temperature=0.3,
                        response_mime_type="application/json",
                        response_schema=AIResponseSchema,
                    ),
                )
                break
            except Exception as e:
                print(e)
                continue

        if not response:
            raise RuntimeError("Failed to generate the AI response.")

        print(response.text)
        parsed_response = json.loads(response.text)
        return parsed_response

    def generate_response_stream(
        self,
        user_query,
        sources: str,
        uploaded_files: list = [],
        chat_history: list = [],
        student_info: dict = {},
    ):
        contents, system_instructions = self.ai_instructions(
            user_query,
            sources,
            uploaded_files,
            chat_history,
            student_info,
            output_format="text_stream",
        )

        stream = None

        for model in [
            GEMINI_MODELS_CODES["3.5-flash-lite"],
            GEMINI_MODELS_CODES["2.5-flash-lite"],
            GEMINI_MODELS_CODES["3.6-flash"],
        ]:
            try:
                stream = self.gemini_client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instructions,
                        max_output_tokens=40000,
                        temperature=0.7,
                    ),
                )

                # Pure text stream generator
                for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                print(e)
                continue

        if not stream:
            raise RuntimeError("Failed to generate the AI response.")

    @staticmethod
    def ai_instructions(
        user_query: str,
        sources: str,
        uploaded_files: list = [],
        chat_history: list = [],
        student_info: dict = {},
        output_format: Literal["text_stream", "json"] = "text_stream",
    ) -> tuple[list[types.Content], str]:

        # Get user info
        name = student_info.get("name", "Unknown")
        grade = student_info.get("grade", "Unknown")

        # Handle output format instructions
        if output_format == "text_stream":
            output_format_txt = (
                "You MUST return your response as raw Markdown formatted text."
            )

        elif output_format == "json":
            output_format_txt = """You MUST return your response as a JSON object strictly following this structure:
{
    "response": "Your full Markdown-formatted answer here...",
    "suggested_chat_title": "A short, concise 2-5 word title summarizing the user query"
}"""

        system_instructions = f"""
You are an expert AI RAG Study Assistant for LearnPeak, an educational platform dedicated to helping students learn from their curricula textbooks.
Your goal is to provide accurate, clear, and highly structured educational answers to the student's questions.

==================================================
PLATFORM REFERENCE INFORMATION
==================================================

Use the factual data in this section ONLY when the student explicitly asks questions regarding the LearnPeak platform, its founder, or its core features.
Do NOT output platform metadata or list platform modules during standard user interactions or simple greetings.
If the student requests extended platform background, direct them to the dedicated About Page in the application menu.

Overview:
LearnPeak is a curriculum-centric educational software platform designed to deliver personalized academic assistance aligned directly with official school textbooks.

Core Features:
- Ask Your Book: Retrieval-augmented QA grounded in curriculum textbook content.
- Learn with AR: Interactive 3D models and augmented reality visualizations for conceptual learning.
- Quiz Generation: Automated assessment creation derived from specific textbook units, lessons, or supplementary sources.
- Study Strategies: Implementation of evidence-based learning methodologies, including active recall, spaced repetition, and elaboration.

Founder & Developer:
- Ibrahim Mohamed (Founder & Lead Developer)
- Professional Profiles:
* LinkedIn: https://www.linkedin.com/in/ibrahim-mo-dev/
* GitHub: https://github.com/el-ibrahim-mohamed/

Technical Engine:
- Model Architecture: Powered by Google Gemini AI models optimized for high-speed, structured educational reasoning.

==================================================
CAPABILITIES & CORE SCOPE
==================================================

You are the AI Chat Assistant inside LearnPeak ("Ask Your Book").

You can assist students and teachers with:
- Explaining textbook concepts, rules, and definitions with structural clarity.
- Providing direct answers grounded in retrieved textbook source materials.
- Creating summaries, key bullet points, or comparison tables
- Grading user-submitted images of handwritten answers in their books or worksheets.
- Answering general knowledge academic questions when textbook sources lack context.
- Helping students with any creative questions sparked by curriosity in their studies using the power of AI.

==================================================
STUDENT PROFILE
==================================================
- Student Name: {name}
- Grade: {grade}

==================================================
GROUNDING RULES & SOURCE HANDLING
==================================================

1. IF THE ANSWER IS FULLY FOUND IN THE SOURCES OR EXPANDS ON SOURCE CONCEPTS:
- Rely strictly on the information provided in the SOURCES section to address the student's question.
- When answering questions do not 'add' more words than the literal written answers in the book.
- If the student requests further explanations, simpler breakdowns, deeper notes, or  clarifications regarding
    concepts, terms, or rules present in the sources, answer normally without issuing any missing-source warnings.
- Do NOT introduce speculative facts or unverified content outside the scope of the subject matter.

2. IF NO RELEVANT SOURCES ARE PROVIDED OR THE SOURCES LACK REQUIRED CONTEXT:
- Explicitly inform the student (in the primary language of their query) that no matching source material was retrieved for their specific query.
- Clarify that the application retrieves better, more relevant sources when selecting filters (such as Unit, Lesson, or Subject).
- Strongly suggest that the user select correct and detailed filters (e.g., selecting the specific Unit and Lesson from the dropdown/filter options) so the system can pull the exact textbook pages required.
- Users should only upload their pages or write them if it is not found in the added books in our DB, let them check out the "Added Books" page.
- After providing this recommendation, answer their question using general knowledge while clearly indicating that the answer comes from general knowledge rather than their official textbook.

==================================================
MATHEMATICS, OCR CORRECTION & LATEX GUIDELINES
==================================================

1. OCR ERROR CORRECTION:
- Input sources or user queries may contain minor Optical Character Recognition (OCR) errors or broken symbols (e.g., misread variable names, missing operators, garbled exponent notation).
- Silently correct minor transcription flaws using canonical mathematical logic, standard symbols, and domain context before solving.
- Do not explicitly point out or comment on minor OCR errors unless doing so is strictly necessary to explain a correction in logic.

2. LATEX FORMATTING & STREAMLIT COMPATIBILITY (`st.markdown`):
- All mathematical expressions, numbers with roots/powers, equations, and standalone variables MUST use valid LaTeX syntax.
- INLINE MATH: Enclose strictly within SINGLE dollar signs: $expression$.
    - INVALID: $$(5)^{{\\frac{{1}}{{2}}}}$$ or $\\sqrt{{3}}$$or$$\\sqrt{{3}}$|
    - VALID: $\\sqrt{{3}}$ or $5^{{\\frac{{1}}{{2}}}}$
- DISPLAY/BLOCK MATH: Place on its own dedicated line enclosed in DOUBLE dollar signs:$$expression$$
- STRICT DELIMITER MATCHING: Never mix single and double dollar signs (e.g., NEVER start with$$and end with$).
- ESCAPING: Use explicit LaTeX commands inside dollar signs (e.g., `\\frac`, `\\times`, `\\sqrt`). Never leave dangling pipe characters (`|`) or unmatched braces `{{}}`.
- Operator Symbols: Use explicit LaTeX commands for symbols instead of plaintext approximations (e.g., use `\\times` for multiplication rather than `x` or `*`, `\\div` for division, `\\leq` / `\\geq` for inequalities).

3. DIAGRAM-DEPENDENT QUESTIONS:
- If a student asks a mathematical or visual question that directly references a diagram, figure, graph, or geometric layout that is absent from the text input, inform them concisely that you can currently process text context only.
- Instruct the student briefly to take a clear photo or screenshot of the diagram/question and upload the image directly in the chat for visual evaluation.

==================================================
FORMATTING & TONE RULES
==================================================

- TONE: Friendly, supportive, clear, and academically encouraging.
- MARKDOWN: Use bolding for key terminology, ordered lists for sequential workflows, and Markdown headers (`###`) for structural breakdown.
- COMPARISONS: Use Markdown tables for structural comparisons across concepts, mathematical formulas, or historical events.
- LINE BREAKS (IMPORTANT): When breaking lines, always use double line breaks (or standard Markdown lists like ol / ul), because a single line break is ignored by the Markdown renderer.
- CITATIONS: 
* If and ONLY IF information from the provided textbook sources was used, you MUST append a "Sources:" section at the very end of your response.
* Format citations strictly as follows:

Sources:
• {{Subject}} - Unit {{unit_num}} - Lesson {{lesson_num}} - Page {{page_num}}

Example:
Sources:
• Science - Unit 1 - Lesson 3 - Page 58 to 62

* Do NOT include source citations if the answer was generated entirely from general knowledge.

==================================================
OUTPUT REQUIREMENT
==================================================

{output_format_txt}

Now, answer the student's question.
"""

        # --------------------------------------------------
        # Build Contents List
        # --------------------------------------------------
        contents: list[types.Content] = []

        # 1. Process Chat History Turns
        for msg in chat_history:
            role = "user" if msg.get("role") == "user" else "model"
            parts = []

            # Add text content if available
            if msg.get("content"):
                parts.append(types.Part.from_text(text=msg["content"]))

            # Add past file attachments using URI references
            if msg.get("files"):
                for file_info in msg["files"]:
                    if file_info.get("gemini_file_uri") and file_info.get("mime_type"):
                        parts.append(
                            types.Part.from_uri(
                                file_uri=file_info["gemini_file_uri"],
                                mime_type=file_info["mime_type"],
                            )
                        )

            if parts:
                contents.append(types.Content(role=role, parts=parts))

        # 2. Process Current User Input & Sources
        sources_text = (
            sources.strip()
            if sources and sources.strip()
            else "No relevant textbook sources found. Ask the user to make correct,"
            "detailed filters. Tell the user if his exact book is not found, he can"
            "request to add it in the added books page."
        )

        current_prompt = f"""==================================================
SOURCES
==================================================
{sources_text}

==================================================
CURRENT USER PROMPT
==================================================
{user_query}"""

        current_turn_parts = []

        # Add current turn file attachments
        if uploaded_files:
            for file_info in uploaded_files:
                if file_info.get("gemini_file_uri") and file_info.get("mime_type"):
                    current_turn_parts.append(
                        types.Part.from_uri(
                            file_uri=file_info["gemini_file_uri"],
                            mime_type=file_info["mime_type"],
                        )
                    )

        # Append structured current user prompt text
        current_turn_parts.append(types.Part.from_text(text=current_prompt))

        # Append final user turn to contents list
        contents.append(types.Content(role="user", parts=current_turn_parts))

        # Debug save
        with open("prompt.txt", "w", encoding="utf-8") as f:
            f.write(current_prompt)

        return contents, system_instructions

    @staticmethod
    def sanitize_latex(text: str) -> str:
        """
        Cleans up LLM-generated LaTeX output specifically for Streamlit's st.markdown parser.
        """
        if not text:
            return ""

        # 1. Strip accidental trailing markdown/pipe artifacts right after closing delimiters
        # E.g., "$$\sqrt{3}$|" or "$\sqrt{3}$|" -> "$\sqrt{3}$"
        text = re.sub(r"(\${1,2}[^$\n]+?\${1,2})\|+", r"\1", text)

        # 2. Fix mismatched delimiters on same-line expressions
        # Case A: Started with $$ but closed with $ (e.g., $$(5^{\frac{1}{2}})^6 = 125$)
        text = re.sub(r"(?<!\$)\$\$(?!\$)(.*?)(?<!\$)\$(?!\$)", r"$\1$", text)

        # Case B: Started with $ but closed with $$ (e.g., $(5^{\frac{1}{2}})^6 = 125$$)
        text = re.sub(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$\$(?!\$)", r"$\1$", text)

        # 3. Clean up display math ($$) to ensure proper newline isolation for Streamlit
        # Streamlit requires $$ block math to be separated from prose by newlines
        def fix_block_math(match):
            content = match.group(1).strip()
            return f"\n\n$$\n{content}\n$$\n\n"

        # Isolates inline block math like "$$ e=mc^2 $$" onto dedicated lines
        text = re.sub(r"\$\$\s*(.*?)\s*\$\$", fix_block_math, text, flags=re.DOTALL)

        # 4. Remove any multi-newline padding created by block math isolation
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text


class AddSource:
    def __init__(
        self,
        rag_service: RagService,
        mistral_api_key: str,
    ):
        self.rag_service = rag_service
        self.mistral_client: Mistral = Mistral(api_key=mistral_api_key)
        self.gemini_client = rag_service.gemini_client

    def split_pdf_by_size(self, pdf_bytes: bytes, max_mb: int = 45) -> list[bytes]:
        """
        Split a PDF into page-based chunks using an average-page-size estimate.

        The function avoids repeatedly serializing a growing PDF. It first
        estimates the number of pages that should fit in each chunk, then
        serializes each chunk and adjusts the boundary only when necessary.

        A single page larger than max_mb is returned as its own chunk.
        """

        max_bytes = max_mb * 1024 * 1024

        if len(pdf_bytes) <= max_bytes:
            return [pdf_bytes]

        source_pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        try:
            total_pages = len(source_pdf)

            if total_pages == 0:
                return [pdf_bytes]

            # Estimate the average serialized size per page.
            avg_page_bytes = len(pdf_bytes) / total_pages

            # Initial estimate of how many pages should fit in one chunk.
            pages_per_chunk = max(1, int(max_bytes / avg_page_bytes))

            chunks = []
            start_page = 0

            while start_page < total_pages:
                end_page = min(start_page + pages_per_chunk, total_pages)

                while True:
                    doc = pymupdf.open()

                    try:
                        doc.insert_pdf(
                            source_pdf,
                            from_page=start_page,
                            to_page=end_page - 1,
                        )

                        chunk_bytes = doc.tobytes(
                            garbage=3,
                            deflate=True,
                        )

                    finally:
                        doc.close()

                    # Chunk fits.
                    if len(chunk_bytes) <= max_bytes:
                        chunks.append(chunk_bytes)
                        start_page = end_page
                        break

                    # Even one page is too large.
                    if end_page - start_page == 1:
                        chunks.append(chunk_bytes)
                        start_page = end_page
                        break

                    # Chunk is too large. Estimate how much to shrink it.
                    actual_avg = len(chunk_bytes) / (end_page - start_page)

                    new_page_count = max(1, int(max_bytes / actual_avg))

                    # Make sure we actually reduce the range.
                    new_page_count = min(new_page_count, (end_page - start_page) - 1)

                    end_page = start_page + new_page_count

            return chunks

        finally:
            source_pdf.close()

    def prepare_pdf(self, pdf_bytes: bytes, category: str = None):
        """
        Analyzes a PDF chunk via Gemini to extract page ranges and digital-to-actual page mapping.
        Does NOT alter or re-slice the input PDF bytes.
        """

        # Upload the PDF using the Files API
        def upload_pdf():
            if len(pdf_bytes) >= 15 * 1024 * 1024:
                return self.gemini_client.files.upload(
                    file=BytesIO(pdf_bytes),
                    config=types.UploadFileConfig(
                        mime_type="application/pdf", display_name="Book PDF"
                    ),
                )
            else:
                return types.Part.from_bytes(
                    data=pdf_bytes, mime_type="application/pdf"
                )

        book_pdf = upload_pdf()

        # English Category
        get_english_category = False
        if category == "ol":
            get_english_category = True

        # Create system instructions
        system_instructions = f"""
You are an AI system responsible for analyzing an educational textbook PDF and extracting its structural information for an automated educational-content ingestion pipeline.
Your task is to analyze the provided PDF and return ONLY the required JSON object.

---

## 1. Identify the Main Book

The provided PDF may contain multiple books merged into a single PDF. For example, it may contain:

- The Main Book / primary textbook
- Notes Book
- Guide / Answer Book
- Revision Book
- Other supplementary material

Your task is to analyze ONLY the Main Book: the primary textbook containing the explanations, lessons, and exercises intended to be learned.
First determine the boundaries of the Main Book within the PDF. Completely ignore all other books and supplementary material.
Do not assume that the Main Book is necessarily the first book in the PDF. Identify it from its title, structure, headers, footers, content, and other contextual clues.

---

## 2. Understand Digital and Actual Page Numbers

There are two different page-number systems:

- Digital page number: the page's position/number within the PDF.
- Actual page number: the page number printed on the physical textbook page, usually visible in the footer.

All `start_page` and `end_page` values in the output MUST use digital page numbering, never the printed actual page numbering.

---

## 3. Determine The Pages Offset

Determine the constant offset between these two numbering systems within the Main Book.

To determine the offset, inspect a suitable page of the Main Book that is NOT near the beginning of the book. Identify:

1. Its digital/PDF page number.
2. Its printed actual page number from the textbook.
3. Calculate:

actual page number - digital page number = offset

For example, if digital page 10 corresponds to printed page 14:
14 - 10 = 4

Therefore:
`"digital_to_actual_pages_offset": 4`

The offset is constant throughout the Main Book.
The offset MUST be returned as an integer, such as 4, 0, or -2.
Do not attempt to return separate offsets for different sections.

---

## 4. Determine Unit and Lesson Metadata

For every pages range, determine:
{"- Category (REQUIRED)" if get_english_category else ""}
- Unit number (REQUIRED)
- Unit name
- Lesson(s) number(s) (REQUIRED)
- Lesson(s) name(s)

The unit and lesson information should primarily be determined from the headers and/or footers of the Main Book pages, where this information is provided.
The unit_number and lesson_number MUSTN'T be null.
Preserve the names as they appear in the textbook.

{"""English O.L books have 2 sections, the main units and the O.L Story. The options for `category` are either 'ol' or 'ol_story'.
For the O.L story, consider the unit_num the next one if not specified and consider the lesson_num the chapters numbers.""" if category else ""}

Use surrounding pages when necessary to correctly determine which unit and lesson a range belongs to.
The metadata applies to every page within the range.

Put lesson_num and lesson_name in lists, for example:
- lesson_num: [1]
- lesson_name: ["Lesson 1 Name"]

IMPORTANT: Some pages may cover TWO or more lessons together. When a page range explicitly belongs to multiple lessons,
include ALL applicable lesson numbers and lesson names in `lesson_num` and `lesson_name` as lists.

For example, if a page covers "Lesson 1 & 2", return:
- lesson_num: [1, 2]
- lesson_name: ["Lesson 1 Name", "Lesson 2 Name"]

Do NOT create a combined lesson number or combined lesson name such as `"1 & 2"` or `"Lesson 1 & 2"`.

### LESSON PAGE BOUNDARIES & OVERLAPS
1. Shared Pages Are Expected: A single page (e.g., Page 12) can contain the end of Lesson 1 AND the beginning of Lesson 2.
2. Inclusive Overlapping Ranges: When two lessons share a page, BOTH lessons MUST include that shared page in their range.
   - Example: If Lesson 1 starts on page 10 and ends halfway down page 12, its range is start_page: 10, end_page: 12.
   - If Lesson 2 starts on the lower half of page 12 and ends on page 15, its range is start_page: 12, end_page: 15.
   - Both entries sharing page 12 is correct and intended. Do NOT skip page 12 for Lesson 2 or artificially increment the start page to 13.
3. Multi-Lesson Sections: If an assessment section explicitly targets multiple lessons simultaneously (e.g., "Lessons 1 & 2 Test"), emit separate metadata entries for each lesson cited, sharing the exact same start_page and end_page range.

--- CUSTOM CASES ---
In ARABIC books ONLY, grammar, spelling, and writing units can be separate from the main readin lessons.
Each one of them should be considered as a separate unit and their unit_num should be continuing on the reading units.

---

## 5. Page Ranges

A lesson range usually includes explanation pages and excercises/questions pages.
All ranges MUST be expressed using digital/PDF page numbers.
`start_page` is the first digital page included in the lesson range.
`end_page` is the last digital page included in the lesson range.

IMPORTANT: Only include ranges of lessons. Do NOT include ranges of unit reviews, book intro/outro,
or any range whose unit and lesson metadata does not belong to it.

Do not use printed page numbers for these fields.
Return ranges in ascending digital-page order.
Do not overlap ranges.
Do not include pages outside the Main Book.

---

## 6. Required Output

Return ONLY valid JSON matching exactly the structure in this example:

{{
  "digital_to_actual_pages_offset": 4,
  "pages_ranges": [
    {{
      "start_page": 23,
      "end_page": 34,
      "unit_name": "Generations",
      "unit_num": 1,
      "lesson_name": ["Thermal and Chemical Changes"],
      "lesson_num": [2],
      {"'category': 'ol'," if get_english_category else ""}
    }},
    {{
      "start_page": 51,
      "end_page": 73,
      "unit_name": "Discover Yourself",
      "unit_num": 2,
      "lesson_name": ["Lesson 1 Name", "Lesson 2 Name"],
      "lesson_num": [1, 2],
      {"'category': 'ol'," if get_english_category else ""}
    }}
  ]
}}

The top-level object MUST contain exactly these two keys:

- `digital_to_actual_pages_offset`
- `pages_ranges`

Each dict in `pages_ranges` MUST contain exactly these keys:

- `start_page`
- `end_page`
{"- `category`" if get_english_category else ""}
- `unit_name`
- `unit_num`
- `lesson_name`
- `lesson_num`

Data types MUST be:

- `digital_to_actual_pages_offset`: integer
- `start_page`: integer
- `end_page`: integer
{"- `category`: str" if get_english_category else ""}
- `unit_name`: string
- `unit_num`: integer
- `lesson_name`: list of strings
- `lesson_num`: list of integers

Do not wrap the JSON in Markdown code fences.
Do not include any additional keys.
Do not include any explanation before or after the JSON.
"""

        # Send request to Gemini
        response = None
        for model in GEMINI_FLASH_FIRST:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=[book_pdf],
                    config=types.GenerateContentConfig(
                        system_instruction=system_instructions,
                        temperature=0.3,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(
                            thinking_level="low",
                            include_thoughts=False,
                        ),
                    ),
                )
                break
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue

        if not response:
            raise RuntimeError("All Gemini models failed to generate content.")

        json_response = json.loads(response.text)

        offset: int = json_response["digital_to_actual_pages_offset"]
        pages_ranges: list = json_response["pages_ranges"]

        # Open source PDF chunk to inspect total pages
        source_pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        total_chunk_pages = len(source_pdf)

        digital_to_actual_mapping = {}
        pages_metadata = {}

        for page_range in pages_ranges:
            start_page = page_range["start_page"]
            end_page = page_range["end_page"]

            # Validate range bounds
            if start_page < 1 or end_page > total_chunk_pages or start_page > end_page:
                raise ValueError(
                    f"Invalid page range returned by Gemini: {start_page}-{end_page}. "
                    f"The PDF contains {total_chunk_pages} pages."
                )

            # Map raw digital page numbers directly to actual page numbers & metadata
            for digital_page in range(start_page, end_page + 1):
                actual_page = digital_page + offset

                digital_to_actual_mapping[digital_page] = actual_page

                pages_metadata[actual_page] = {
                    "unit_name": page_range["unit_name"],
                    "unit_num": page_range["unit_num"],
                    "lesson_name": page_range["lesson_name"],
                    "lesson_num": page_range["lesson_num"],
                }

                # if page_range.get("category"):
                #     pages_metadata[actual_page]["category"] = page_range["category"]
                # elif category and not get_english_category:
                #     pages_metadata[actual_page]["category"] = category

                pages_metadata[actual_page]["category"] = category

        source_pdf.close()

        return digital_to_actual_mapping, pages_metadata

    def ocr_pdf(self, pdf_bytes: bytes, pages_mapping: dict) -> list[dict]:
        """
        Perform OCR on a PDF document using Mistral OCR and extract the text of each page.

        The PDF is sent to the Mistral OCR API directly from its bytes. For each page,
        the function extracts the page's Markdown content and footer, maps its digital
        page number to its actual page number from the footer, and returns a list containing
        the actual page number and its corresponding OCR text.

        Parameters
        ----------
        pdf_bytes : bytes
            The raw bytes of the PDF document to process.
        pages_mapping : dict
            The dictionary mapping the digital page number to the actual page number.

        Returns
        -------
        list[dict]
            A list of dictionaries, one for each page, in the following format:

            [
                {
                    "page_num": int | None,
                    "page_text": str,
                },
                ...
            ]

            - "page_num" is the extracted page number from the footer, or None if no valid
            page number could be identified.
            - "page_text" is the OCR-extracted page content in Markdown format.

        Notes
        -----
        - OCR is performed using the `mistral-ocr-latest` model.
        - Footer extraction is enabled to recover the original page numbers printed in the document.
        """

        def extract_page_number(footer_text: str):
            """
            Extract the real page number from a page footer.

            The function looks for a standalone integer at the beginning or end of the
            footer text (where page numbers are expected to appear). Returns the page
            number as an integer, or None if no valid page number is found.
            """

            footer_text = footer_text.strip()

            start = re.match(r"^(\d+)\b", footer_text)
            if start:
                return int(start.group(1))

            end = re.search(r"\b(\d+)$", footer_text)
            if end:
                return int(end.group(1))

            return None

        # 1. Upload the raw PDF bytes directly to Mistral's storage
        uploaded_file = self.mistral_client.files.upload(
            file={
                "file_name": "document.pdf",
                "content": pdf_bytes,  # Pass raw bytes directly (0% Base64 bloat)
            },
            purpose="ocr",
        )

        try:
            # 2. Generate a temporary internal signed URL for the OCR tool
            signed_url_response = self.mistral_client.files.get_signed_url(
                file_id=uploaded_file.id
            )

            # 3. Process the OCR using the lightweight signed URL
            response = self.mistral_client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": signed_url_response.url,
                },
                include_blocks=False,
                extract_header=True,
                extract_footer=True,
            )

        finally:
            # 4. Clean up the scratch space file immediately to prevent leaks
            self.mistral_client.files.delete(file_id=uploaded_file.id)

        # Save the respoonse for debugging and reuse
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        json_filename = f"debug/ocr/{timestamp}.json"

        try:
            with open(json_filename, "w", encoding="utf-8") as f:
                f.write(response.model_dump_json(indent=4))
        except:
            pass

        # Loop over the pages
        results = []
        for page in response.pages:
            extracted_text = page.markdown
            # footer_text = page.footer

            # page_num = extract_page_number(footer_text)
            page_num = pages_mapping[page.index + 1]

            results.append(
                {
                    "page_num": page_num,
                    "page_text": extracted_text,
                }
            )

        return results

    def extract_ocr_from_zip(
        self, zip_bytes: bytes, pages_mapping: dict, chunk_num: int
    ) -> list[dict]:
        """
        Extract OCR markdown content for a specific chunk (by chunk_num) from a master Document AI ZIP download.
        Dynamically locates the root directory containing 'chunk_{chunk_num}' or 'chunk_{chunk_num}_'.
        Reads markdown files corresponding only to valid digital pages in pages_mapping.
        """
        results = []

        with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
            all_files = z.namelist()

            # Target identifier for this chunk's folder (e.g. "chunk_1")
            chunk_target = f"chunk_{chunk_num}"

            for digital_page, actual_page in pages_mapping.items():
                # End pattern for page markdown file inside Document AI zip
                page_suffix = f"pages/page-{digital_page}/markdown.md"

                # Find file path that contains the chunk_target AND ends with page_suffix
                matched_file = next(
                    (
                        f
                        for f in all_files
                        if chunk_target in f and f.endswith(page_suffix)
                    ),
                    None,
                )

                if matched_file:
                    page_text = z.read(matched_file).decode("utf-8")
                    results.append(
                        {
                            "page_num": actual_page,
                            "page_text": page_text,
                        }
                    )
                else:
                    print(
                        f"Warning: Could not find chunk_{chunk_num} page-{digital_page} markdown in ZIP."
                    )

        return results

    def attach_metadata(
        self,
        ocr_result: list[dict],
        batch_id: str,
        unit_lesson_metadata: dict,
        grade: str,
        subject: str,
        book_publisher: str = "el-moasser",
        country: str = "egypt",
        education: str = "national",
        term: int = None,
    ):
        """
        Attach subject, publisher, unit, and lesson metadata to each OCR page.

        Parameters
        ----------
        ocr_result : list[dict]
            The output of `ocr_pdf()`.
        subject : str
            The subject of the book.
        book_publisher : str
            The publisher of the book.
        unit_lesson_input : str
            The page-to-unit/lesson mapping entered by the user.

        Returns
        -------
        list[dict]
            The OCR result with metadata attached to every page.
        """

        # Detect term fallback
        if not term:
            term = self.current_term()

        data = ocr_result

        # Attach metadata to each OCR page
        for page_data in data:
            current_metadata = unit_lesson_metadata.get(page_data["page_num"])

            page_data.update(
                {
                    "batch_id": batch_id,
                    "country": country,
                    "education": education,
                    "grade": grade,
                    "term": term,
                    "subject": subject,
                    "book_publisher": book_publisher,
                    **current_metadata,
                }
            )

        return data

    def chunk_pages(self, pages: list[dict]):
        """
        Split each OCR page into sentence-aware chunks while preserving metadata.

        Each page is preprocessed, split into chunks of approximately the target
        size, and converted into an independent chunk with a unique UUID. All page
        metadata is copied to every chunk.

        Parameters
        ----------
        pages : list[dict]
            The output of `attach_metadata()`.

        Returns
        -------
        list[dict]
            A list of chunk dictionaries.
        """

        TARGET_SIZE = 500  # characters

        def preprocess(text: str) -> str:
            """Preprocess page text before chunking."""
            return text

        def split_into_chunks(text: str) -> list[str]:
            """
            Split text into chunks of approximately TARGET_SIZE characters.

            The splitter attempts to end each chunk at the nearest sentence
            boundary after the target size. If none is found, it cuts exactly at
            the target size.
            """

            text = text.strip()

            if len(text) <= TARGET_SIZE:
                return [text]

            chunks = []
            start = 0

            while start < len(text):
                end = start + TARGET_SIZE

                if end >= len(text):
                    chunks.append(text[start:].strip())
                    break

                # Search for the nearest sentence ending after the target size.
                match = re.search(r"[,.!?]\s+", text[end:])

                if match:
                    end += match.end()
                else:
                    end = min(end, len(text))

                chunks.append(text[start:end].strip())
                start = end

            return chunks

        results = []

        for page in pages:
            page_text = preprocess(page["page_text"])
            chunks = split_into_chunks(page_text)

            # Remove the page_text key as it will be replaced by chunk_txt
            page.pop("page_text")

            for chunk_order, chunk_text in enumerate(chunks):
                results.append(
                    {
                        "id": str(uuid.uuid4()),
                        "chunk_text": chunk_text,
                        "chunk_order": chunk_order,
                        **page,
                    }
                )

        return results

    def insert_to_vector_db(
        self,
        chunks: list[dict],
    ):
        """
        Insert a list of chunks into the vector database.

        Each chunk is embedded and uploaded to the configured Qdrant collection
        through the RagService.

        Parameters
        ----------
        chunks : list[dict]
            The output of `chunk_pages()`.

        Returns
        -------
        None
        """

        self.rag_service.insert_batch(chunks)

    def add_source(
        self,
        pdf_bytes: bytes,
        grade: str,
        subject: str,
        book_publisher: str = "el-moasser",
        english_category: str = None,
        ignore_index: int = None,
    ):
        """
        Process a PDF book and add it to the vector database.

        Yields
        ------
        dict
            Progress information for each completed pipeline step.
            Each message contains:
            - step: Human-readable step name
            - message: Detailed status message
            - elapsed: Time taken in seconds
        """

        batch_id = str(uuid.uuid4())

        # ---------------------------------------------------------
        # SPLIT PDF
        # ---------------------------------------------------------

        start = time.perf_counter()

        pdf_chunks = self.split_pdf_by_size(pdf_bytes)
        if ignore_index is not None and ignore_index < len(pdf_chunks):
            pdf_chunks = [
                chunk for i, chunk in enumerate(pdf_chunks) if i != ignore_index
            ]

        split_time = time.perf_counter() - start

        yield {
            "step": "PDF Split",
            "message": f"PDF split into {len(pdf_chunks)} processing chunk(s).",
            "elapsed": split_time,
        }

        # ---------------------------------------------------------
        # PROCESS EACH PDF CHUNK
        # ---------------------------------------------------------

        for i, chunk_bytes in enumerate(pdf_chunks):

            chunk_number = i + 1
            total_chunks = len(pdf_chunks)

            yield {
                "step": f"Chunk {chunk_number}/{total_chunks}",
                "message": f"Starting processing of chunk {chunk_number} of {total_chunks}.",
                "elapsed": 0,
            }

            # -----------------------------------------------------
            # PREPARE PDF
            # -----------------------------------------------------

            start = time.perf_counter()

            book_pdf_bytes, digital_to_actual_mapping, pages_metadata = (
                self.prepare_pdf(chunk_bytes, english_category)
            )

            elapsed = time.perf_counter() - start

            yield {
                "step": "PDF Prepared",
                "message": (
                    f"Chunk {chunk_number}/{total_chunks} prepared successfully."
                ),
                "elapsed": elapsed,
            }

            # -----------------------------------------------------
            # OCR
            # -----------------------------------------------------

            start = time.perf_counter()

            pages = self.ocr_pdf(
                book_pdf_bytes,
                digital_to_actual_mapping,
            )

            elapsed = time.perf_counter() - start

            yield {
                "step": "OCR Completed",
                "message": (
                    f"Extracted text from {len(pages)} page(s) "
                    f"of chunk {chunk_number}/{total_chunks}."
                ),
                "elapsed": elapsed,
            }

            # -----------------------------------------------------
            # ATTACH METADATA
            # -----------------------------------------------------

            start = time.perf_counter()

            pages = self.attach_metadata(
                pages,
                batch_id=batch_id,
                unit_lesson_metadata=pages_metadata,
                grade=grade,
                subject=subject,
                book_publisher=book_publisher,
                term=1,
            )

            elapsed = time.perf_counter() - start

            yield {
                "step": "Metadata Attached",
                "message": (f"Added curriculum metadata to {len(pages)} page(s)."),
                "elapsed": elapsed,
            }

            # -----------------------------------------------------
            # CHUNK PAGES
            # -----------------------------------------------------

            start = time.perf_counter()

            chunks = self.chunk_pages(pages)

            elapsed = time.perf_counter() - start

            yield {
                "step": "Semantic Chunking Completed",
                "message": (
                    f"Created {len(chunks)} semantic chunk(s) "
                    f"from chunk {chunk_number}/{total_chunks}."
                ),
                "elapsed": elapsed,
            }

            # -----------------------------------------------------
            # INSERT INTO VECTOR DB
            # -----------------------------------------------------

            start = time.perf_counter()

            self.insert_to_vector_db(chunks)

            elapsed = time.perf_counter() - start

            yield {
                "step": "Vector Database Updated",
                "message": (
                    f"Inserted {len(chunks)} chunk(s) into the vector database."
                ),
                "elapsed": elapsed,
            }

        # ---------------------------------------------------------
        # FINISHED
        # ---------------------------------------------------------

        yield {
            "step": "Completed",
            "message": "Book processing and ingestion completed successfully.",
            "elapsed": 0,
            "batch_id": batch_id,
        }

    def add_source_from_zips(
        self,
        pdf_bytes: bytes,
        master_zip_bytes: bytes,
        grade: str,
        subject: str,
        book_publisher: str = "el-moasser",
        category: str = "external_book",
        ignore_index: int = None,
    ):
        """
        Process a PDF book alongside a single Master Document AI ZIP file containing all chunk folders.
        """
        batch_id = str(uuid.uuid4())

        # 1. Split full PDF into chunks
        start = time.perf_counter()
        pdf_chunks = self.split_pdf_by_size(pdf_bytes)

        if ignore_index is not None and ignore_index < len(pdf_chunks):
            pdf_chunks = [
                chunk for i, chunk in enumerate(pdf_chunks) if i != ignore_index
            ]

        split_time = time.perf_counter() - start
        yield {
            "step": "PDF Split",
            "message": f"PDF split into {len(pdf_chunks)} processing chunk(s).",
            "elapsed": split_time,
        }

        # 2. Process each chunk against the Master ZIP
        for i, chunk_bytes in enumerate(pdf_chunks):
            chunk_number = i + 1
            total_chunks = len(pdf_chunks)

            yield {
                "step": f"Chunk {chunk_number}/{total_chunks}",
                "message": f"Starting manual processing of chunk {chunk_number} of {total_chunks}.",
                "elapsed": 0,
            }

            # Prepare PDF metadata with Gemini
            start = time.perf_counter()
            digital_to_actual_mapping, pages_metadata = self.prepare_pdf(
                chunk_bytes, category
            )
            elapsed = time.perf_counter() - start

            yield {
                "step": "Metadata Extracted",
                "message": f"Chunk {chunk_number}/{total_chunks} metadata calculated.",
                "elapsed": elapsed,
            }

            # Parse OCR Markdown directly from Master ZIP for this specific chunk_number
            start = time.perf_counter()
            pages = self.extract_ocr_from_zip(
                zip_bytes=master_zip_bytes,
                pages_mapping=digital_to_actual_mapping,
                chunk_num=chunk_number,
            )
            elapsed = time.perf_counter() - start

            yield {
                "step": "ZIP OCR Parsed",
                "message": f"Extracted {len(pages)} valid page(s) from Master ZIP for chunk {chunk_number}/{total_chunks}.",
                "elapsed": elapsed,
            }

            # Attach metadata
            start = time.perf_counter()
            pages = self.attach_metadata(
                pages,
                batch_id=batch_id,
                unit_lesson_metadata=pages_metadata,
                grade=grade,
                subject=subject,
                book_publisher=book_publisher,
                term=1,
            )
            elapsed = time.perf_counter() - start

            yield {
                "step": "Metadata Attached",
                "message": f"Added curriculum metadata to {len(pages)} page(s).",
                "elapsed": elapsed,
            }

            # Chunk Pages
            start = time.perf_counter()
            chunks = self.chunk_pages(pages)
            elapsed = time.perf_counter() - start

            yield {
                "step": "Semantic Chunking Completed",
                "message": f"Created {len(chunks)} semantic chunk(s) from chunk {chunk_number}/{total_chunks}.",
                "elapsed": elapsed,
            }

            # Upsert into Vector DB
            start = time.perf_counter()
            self.insert_to_vector_db(chunks)
            elapsed = time.perf_counter() - start

            yield {
                "step": "Vector Database Updated",
                "message": f"Inserted {len(chunks)} chunk(s) into vector database.",
                "elapsed": elapsed,
            }

        # Completed
        yield {
            "step": "Completed",
            "message": "Manual ZIP ingestion completed successfully.",
            "elapsed": 0,
            "batch_id": batch_id,
        }

    @staticmethod
    def current_term():
        month = datetime.now().month

        if 9 <= month <= 12 or month == 1:
            return 1
        elif 2 <= month <= 5:
            return 2
        else:
            return 1
