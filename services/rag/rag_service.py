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

    def format_search_results(self, chunks_payloads: list[dict]) -> str:
        """
        Formats a list of chunk payload dictionaries into structured textbook text.
        Sorts chunks strictly by curriculum hierarchy and page/chunk sequence.
        Formats list-based lesson/unit numbers into readable natural text.
        """
        if not chunks_payloads:
            return ""

        chunks = list(chunks_payloads)

        def format_num_list(val):
            if isinstance(val, (list, tuple)):
                items = [str(x) for x in val]
                if not items:
                    return "N/A"
                if len(items) == 1:
                    return items[0]
                elif len(items) == 2:
                    return f"{items[0]} & {items[1]}"
                else:
                    return ", ".join(items[:-1]) + f", and {items[-1]}"
            return str(val) if val is not None else "N/A"

        # Sort chunks strictly into textbook order (Publisher excluded from sorting)
        chunks.sort(
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

        for chunk in chunks:
            page = (
                chunk.get("grade"),
                chunk.get("subject"),
                chunk.get("book_publisher"),
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

                subject_display = (
                    get_key_by_value(SUBJECTS, chunk.get("subject"))
                    if chunk.get("subject") in SUBJECTS.values()
                    else chunk.get("subject", "")
                )

                publisher_display = (
                    get_key_by_value(BOOK_PUBLISHERS, chunk.get("book_publisher"))
                    if chunk.get("book_publisher") in BOOK_PUBLISHERS.values()
                    else chunk.get("book_publisher", "")
                )

                unit_str = format_num_list(chunk.get("unit_num"))
                lesson_str = format_num_list(chunk.get("lesson_num"))

                sources_text += (
                    f'=== Grade: {chunk.get("grade", "N/A")} | '
                    f"Subject: {subject_display} | "
                    f"Publisher: {publisher_display} | "
                    f"Unit {unit_str} | "
                    f"Lesson {lesson_str} | "
                    f'Page {chunk.get("page_num", "N/A")} ===\n\n'
                )

                current_page = page

            sources_text += chunk.get("chunk_text", "") + "\n"

        return sources_text.strip()

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

        # Format retrieved chunks using the helper
        return self.format_search_results(chunks_results)

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

        print(rf"{response.text}")
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
        """Build Gemini conversation contents and LearnPeak system instructions."""

        name = student_info.get("name") or "Unknown"
        grade = student_info.get("grade") or "Unknown"

        # --------------------------------------------------
        # System instructions
        # --------------------------------------------------
        system_instructions = f"""
You are LearnPeak's AI Assistant, an expert tutor on an AI learning platform aligned with student curricula and textbooks.

==================================================
## RULES & GUARDRAILS
==================================================

1. You are provided with textbook sources relevant to the student's curriculum. Prioritize these sources above all else when answering.
2. If the correct answer is found within the provided sources, answer the question directly, clearly, and objectively.
3. If the answer (or any part of it) is missing from the textbook sources, you MUST first explicitly declare that this information
   has not been correctly retrieved or is not fully covered in the student's textbook sources, but based on general knowledge... (short and concise)
   You can also suggest choosing correct unit and lesson filters to get better results (short and concise)
   and then you MUST ANSWER directly and correctly.
4. Always give an answer to the student following the previous instructions.
5. Keep all responses concise, structurally organized, direct, and clear for a student.

==================================================
## STUDENT ANSWER CORRECTION INSTRUCTIONS
==================================================

**Activation Condition**
Apply these instructions only when the student has submitted their own answers, either as text in the chat or in an image,
and requests evaluation or correction.
Questions retrieved from textbooks, worksheets, or assessments are not student answers.
If the student only asks you to solve or answer questions, do not apply these grading instructions.

**When grading or correcting student answers:**

1. Map each question correctly and group questions by exercise numbers, letters, or titles as presented in the source material.
2. Use question numbers or letters that match the original layout.
3. For each question, use three distinct lines:
   * [q_num]. [Exact text of the question]
   * **Your Answer:** [The student's submitted answer]
   * **Grading:** [✅ Correct / ❌ Incorrect], followed by a very brief explanation when necessary.
4. **Override Rule:** If the student explicitly requests a different output format, follow their requested format instead.


==================================================
## SOURCE CITATION INSTRUCTIONS
==================================================
At the very end of your response, include a dedicated "Sources" section whenever you use retrieved textbook material. 
Extract the metadata directly from the source headers of the pages you used:
(`=== Grade: ... | Subject: ... | Publisher: ... | Unit ... | Lesson ... | Page ... ===`).

Citation Rules:
1. Group sources by Curriculum, Unit, and Lesson.
2. If multiple consecutive pages or chunks from the same lesson are used, combine them into a single page range
   (e.g., "Pages 13–15" instead of listing page 13, 14, and 15 separately).
3. Keep the citation block brief and clean.

Required Citations Format:
### Sources
- **Book:** [Grade] - [Subject Display] ([Publisher Display])
- **References:** Unit [X], Lesson [Y] (Pages [Start–End] or Page [Z])

==================================================
## MARKDOWN OUTPUT FORMAT
==================================================

1. Format all responses strictly using clean Markdown.
2. Use bolding (**bold**) to emphasize key terms, core concepts, or critical vocabulary.
3. Use bullet points or numbered lists to break down multi-step concepts, definitions, processes, or when answering questions. Do not use dense paragraphs.
4. Use headers (###) to separate different sub-topics if the answer is long or addresses multiple questions.

"""

        # --------------------------------------------------
        # Build Gemini conversation contents
        # --------------------------------------------------
        contents: list[types.Content] = []

        def add_file_parts(parts: list, files: list) -> None:
            """Append accessible Gemini file references to a turn."""
            for file_info in files:
                if not isinstance(file_info, dict):
                    continue

                file_uri = file_info.get("gemini_file_uri")
                mime_type = file_info.get("mime_type")

                if not file_uri or not mime_type:
                    continue

                parts.append(
                    types.Part.from_uri(
                        file_uri=file_uri,
                        mime_type=mime_type,
                    )
                )

        # Previous conversation turns.
        for msg in chat_history:
            if not isinstance(msg, dict):
                continue

            role_value = str(msg.get("role", "")).strip().lower()

            if role_value == "user":
                role = "user"
            elif role_value in ("assistant", "model", "ai"):
                role = "model"
            else:
                # Do not accidentally treat unknown roles as model answers.
                continue

            parts = []

            message_text = msg.get("content")
            if isinstance(message_text, str) and message_text.strip():
                parts.append(types.Part.from_text(text=message_text))

            message_files = msg.get("files")
            if isinstance(message_files, list):
                add_file_parts(parts, message_files)

            if parts:
                contents.append(types.Content(role=role, parts=parts))

        if isinstance(sources, str) and sources.strip():
            sources_text = sources.strip()
        else:
            sources_text = "No relevant textbook sources were retrieved for this turn."

        # --------------------------------------------------
        # Output format
        # --------------------------------------------------
        if output_format == "text_stream":
            output_format_txt = "Return raw Markdown only. Do not wrap the answer in a Markdown code fence."
        elif output_format == "json":
            output_format_txt = """Return exactly one valid JSON object with this structure:
{
    "response": "The complete answer, formatted using Markdown where appropriate.",
    "suggested_chat_title": "A concise 2-5 word title for the current conversation topic"
}"""

        current_prompt = f"""
==================================================
RETRIEVED TEXTBOOK SOURCES
==================================================
The following material was retrieved for the current question.
It may be incomplete or may not support every requested detail.

{sources_text}

==================================================
STUDENT PROFILE
==================================================
- Student Name: {name}
- Grade: {grade}

INSTRUCTIONS FOR PROFILE:
1. Adapt your vocabulary, conceptual depth, and explanations to be perfectly age-appropriate for the student's specified Grade.
2. Greet the Student Name naturally if it is the start of a conversation, but do not repeat their name excessively in every response.

==================================================
OUTPUT FORMAT
==================================================
{output_format_txt}

==================================================
CURRENT STUDENT MESSAGE
==================================================
{user_query}
""".strip()

        # Current user attachments and message.
        current_turn_parts = []
        add_file_parts(current_turn_parts, uploaded_files)

        current_turn_parts.append(types.Part.from_text(text=current_prompt))

        contents.append(
            types.Content(
                role="user",
                parts=current_turn_parts,
            )
        )

        with open("prompt.txt", "w", encoding="utf-8") as f:
            f.write(current_prompt)

        return contents, system_instructions

    @staticmethod
    def sanitize_latex(text: str) -> str:
        """Fixes unescaped Unicode circled numbers inside KaTeX math blocks."""
        if not text:
            return ""

        # Map circled Unicode numbers to raw-string LaTeX text equivalents
        circled_map = {
            "①": r"\text{1.} ",
            "②": r"\text{2.} ",
            "③": r"\text{3.} ",
            "④": r"\text{4.} ",
            "⑤": r"\text{5.} ",
            "⑥": r"\text{6.} ",
            "⑦": r"\text{7.} ",
            "⑧": r"\text{8.} ",
            "⑨": r"\text{9.} ",
            "⑩": r"\text{10.} ",
        }

        def replace_circled_symbols(match: re.Match) -> str:
            block = match.group(0)
            for symbol, replacement in circled_map.items():
                block = block.replace(symbol, replacement)
            return block

        # Replace circled symbols inside display ($$...$$) and inline ($...$) math
        text = re.sub(r"\$\$.*?\$\$", replace_circled_symbols, text, flags=re.DOTALL)
        text = re.sub(r"\$.*?\$", replace_circled_symbols, text)

        return text

    @staticmethod
    def deduplicate_chunks(chunks_payloads: list[dict]) -> list[dict]:
        """
        Deduplicates a list of chunk payload dicts by unique 'id' while maintaining original order.
        """
        seen_ids = set()
        deduped = []
        for chunk in chunks_payloads:
            chunk_id = chunk.get("id")
            if chunk_id:
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    deduped.append(chunk)
            else:
                deduped.append(chunk)
        return deduped


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

To determine the offset, inspect multiple pages of the Main Book that is NOT near the beginning of the book. Identify:

1. Its digital/PDF page number.
2. Its printed actual page number from the textbook.
3. Calculate:

actual page number - digital page number = offset

For example, if digital page 10 corresponds to printed page 14:
14 - 10 = 4

Therefore:
`"digital_to_actual_pages_offset": 4`

And if digital page 14 corresponds to printed page 10:
10 - 14 = -4

Therefore:
`"digital_to_actual_pages_offset": -4`

Then use the other pages to make sure it is correct.

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
                            thinking_level="medium",
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
        self, zip_bytes: bytes, pages_mapping: dict, folder_name: str
    ) -> list[dict]:
        """
        Extract OCR markdown content for a specific chunk folder from a master Document AI ZIP download.
        Matches files inside the target chunk folder path (e.g., 'chunk1_science_prep3.pdf/pages/page-1/markdown.md').
        """
        results = []

        with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
            all_files = z.namelist()

            for digital_page, actual_page in pages_mapping.items():
                # Target path suffix inside the chunk's folder
                page_suffix = f"pages/page-{digital_page}/markdown.md"

                # Find the file that matches the chunk's specific folder_name AND page_suffix
                matched_file = next(
                    (
                        f
                        for f in all_files
                        if folder_name in f and f.endswith(page_suffix)
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
                        f"Warning: Could not find {folder_name} page-{digital_page} markdown in ZIP."
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
        filename: str,
        grade: str,
        subject: str,
        book_publisher: str = "el-moasser",
        category: str = "external_book",
        ignore_index: int = None,
    ):
        """
        Process a PDF book chunk by chunk alongside a single Master Document AI ZIP file containing
        folders named 'chunk{chunk_number}_{filename}' for every chunk.
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

        # 2. Process each chunk against its specific folder in the Master ZIP
        for i, chunk_bytes in enumerate(pdf_chunks):
            chunk_number = i + 1
            total_chunks = len(pdf_chunks)

            # Construct the exact folder name expected inside the ZIP root
            target_folder_name = f"chunk{chunk_number}_{filename}"

            yield {
                "step": f"Chunk {chunk_number}/{total_chunks}",
                "message": f"Starting processing of chunk {chunk_number} of {total_chunks} ({target_folder_name}).",
                "elapsed": 0,
            }

            # Prepare PDF metadata with Gemini
            start = time.perf_counter()
            digital_to_actual_mapping, pages_metadata = self.prepare_pdf(
                chunk_bytes, category
            )
            dig, act = next(
                (k, v)
                for k, v in digital_to_actual_mapping.items()
                if str(k).isdigit() and str(v).isdigit()
            )
            offset = int(act) - int(dig)
            elapsed = time.perf_counter() - start

            yield {
                "step": "Metadata Extracted",
                "message": f"Chunk {chunk_number}/{total_chunks} metadata calculated. Offset: {offset}",
                "elapsed": elapsed,
            }

            # Parse OCR Markdown directly from Master ZIP for target_folder_name
            start = time.perf_counter()
            pages = self.extract_ocr_from_zip(
                zip_bytes=master_zip_bytes,
                pages_mapping=digital_to_actual_mapping,
                folder_name=target_folder_name,
            )
            elapsed = time.perf_counter() - start

            yield {
                "step": "ZIP OCR Parsed",
                "message": f"Extracted {len(pages)} valid page(s) from Master ZIP folder '{target_folder_name}'.",
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
