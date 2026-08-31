import base64
from datetime import datetime
from io import BytesIO
import json
import re
import os
import time
from typing import Literal, Optional
import uuid

import pymupdf
from google import genai
from google.genai import types
from mistralai.client import Mistral
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    MatchAny,
    PointStruct,
)

from services.rag.embedding_service import EmbeddingService
from services.rag.qdrant_service import QdrantService
from config import GEMINI_FLASH_FIRST, GEMINI_LITE_FIRST


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
        self.qdrant_client = qdrant_service.get_client()
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

        self.qdrant_client.upsert(
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

        response = self.qdrant_client.query_points(
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

            points, offset = self.qdrant_client.scroll(
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

    def enrich_sources(
        self, chunks_payloads: list[dict], scope: Literal["page", "lesson"] = "page"
    ) -> str:
        """
        Enriches the retrieved chunks by reconstructing the complete source text.

        Depending on the selected scope, this method retrieves either:
        - The complete pages containing the retrieved chunks ("page").
        - Every page belonging to the lessons containing the retrieved chunks ("lesson").

        The retrieved chunks are sorted according to their location in the textbook,
        then concatenated into a formatted string ready to be passed as context to the LLM.

        Args:
            chunks_payloads (list[dict]):
                The payloads of the chunks returned by semantic search.

            scope (Literal["page", "lesson"], optional):
                Determines how much surrounding context to retrieve.

                - "page": Retrieve only the pages containing the retrieved chunks.
                - "lesson": Retrieve every page belonging to the retrieved lessons.

                Defaults to "page".

        Returns:
            str:
                A formatted string containing the reconstructed source text.
        """

        if not chunks_payloads:
            return ""

        # Metadata fields used to identify a lesson
        metadata_keys = ["country", "education", "subject", "unit_num", "lesson_num"]

        # Page retrieval also requires the page number
        if scope == "page":
            metadata_keys.append("page_num")

        # Collect the unique page/lesson combinations
        combinations = {
            tuple(payload[key] for key in metadata_keys) for payload in chunks_payloads
        }

        # Build one filter for each page/lesson
        filters = Filter(
            should=[
                Filter(
                    must=[
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value),
                        )
                        for key, value in zip(metadata_keys, combination)
                    ]
                )
                for combination in combinations
            ]
        )

        # Retrieve all matching chunks
        chunks_results = self.scroll(filters)

        # Sort them in textbook order
        chunks_results.sort(
            key=lambda chunk: (
                chunk["country"],
                chunk["education"],
                chunk["subject"],
                chunk["unit_num"],
                chunk["lesson_num"],
                chunk["page_num"],
                chunk["chunk_order"],
            )
        )

        # Build the final sources text
        sources_text = ""

        # Used to detect when we've moved to a new page
        current_page = None

        for chunk in chunks_results:

            page = (
                chunk["country"],
                chunk["education"],
                chunk["subject"],
                chunk["unit_num"],
                chunk["lesson_num"],
                chunk["page_num"],
            )

            # If this is the first chunk of a new page, write a header
            if page != current_page:

                # Separate pages with a divider (except before the first page)
                if current_page is not None:
                    sources_text += "\n\n" + "-" * 50 + "\n\n"

                sources_text += (
                    f'=== {chunk["subject"]} | '
                    f'Unit {chunk["unit_num"]} | '
                    f'Lesson {chunk["lesson_num"]} | '
                    f'Page {chunk["page_num"]} ===\n\n'
                )

                current_page = page

            # Add the chunk text
            sources_text += chunk["chunk_text"] + "\n"

        return sources_text.strip()

    def get_sources_from_filters(
        self,
        country: str,
        education: str,
        grade: str,
        subject: str,
        units: list[int] = None,
        lessons: list[int] = None,
    ) -> str:
        """
        Retrieve all textbook chunks matching the selected curriculum filters.

        Unlike semantic search, this retrieves every matching chunk from Qdrant,
        allowing the quiz generator to use an entire book, unit, or lesson.
        """

        conditions = [
            FieldCondition(
                key="country",
                match=MatchValue(value=country),
            ),
            FieldCondition(
                key="education",
                match=MatchValue(value=education),
            ),
            FieldCondition(
                key="grade",
                match=MatchValue(value=grade),
            ),
            FieldCondition(
                key="subject",
                match=MatchValue(value=subject),
            ),
        ]

        if units:
            conditions.append(
                FieldCondition(
                    key="unit_num",
                    match=MatchAny(any=units),
                )
            )

        if lessons:
            conditions.append(
                FieldCondition(
                    key="lesson_num",
                    match=MatchAny(any=lessons),
                )
            )

        query_filter = Filter(must=conditions)

        chunks = self.scroll(query_filter)

        if not chunks:
            return ""

        # Sort everything into textbook order.
        chunks.sort(
            key=lambda chunk: (
                chunk.get("unit_num", 0),
                chunk.get("lesson_num", 0),
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
                    f'=== Book: {chunk.get("book_publisher", "")} {chunk.get("subject")} | '
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

    def generate_response(
        self, user_query, sources: str, chat_history=[], get_chat_title=True
    ):
        prompt = self.ai_prompt(
            user_query, sources, chat_history, get_chat_title, output_format="json"
        )

        for model in GEMINI_LITE_FIRST:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        max_output_tokens=40000,
                        temperature=0.7,
                        response_mime_type="application/json",
                    ),
                )
                break
            except Exception as e:
                print(e)
                continue

        return json.loads(response.text)

    def generate_response_stream(
        self, user_query, sources: str, chat_history: list = [], get_chat_title=False
    ):
        """
        Streaming version of generate_response.
        Returns a generator that yields text chunks as they're generated.
        """
        prompt = self.ai_prompt(
            user_query,
            sources,
            chat_history,
            get_chat_title,
            output_format="text_stream",
        )

        for model in GEMINI_LITE_FIRST:
            try:
                stream = self.gemini_client.models.generate_content_stream(
                    model=model,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        max_output_tokens=40000,
                        temperature=0.7,
                    ),
                )
                # Yield text chunks from the stream
                for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return
            except:
                continue

    @staticmethod
    def ai_prompt(
        user_query: str,
        sources: str,
        chat_history: list = [],
        get_chat_title=False,
        output_format: Literal["text_stream", "json"] = "text_stream",
    ):

        if output_format == "text_stream":
            output_format_txt = "You MUST return your response in markdown format."

        elif output_format == "json" and get_chat_title:
            output_format_txt = """You MUST return your response in a JSON structure like this example:
            {
                "response": "Markdown formatted answer...",
                "suggested_chat_title": "Suggest a chat title based on the first prompt..."
                ],
            }
            """

        return f"""
You are an AI RAG Assistant in an edcational platform called LearnPeak, specialized in school books sources.
Your job is to answer the student's question using ONLY the provided sources.

-----------------------
STRICT RULES
-----------------------

If the full answer is found in the sources:
- You MUST use only the information inside the provided sources (books).
- DO NOT use any external knowledge.
- DO NOT guess or hallucinate.

If the answer (or part of it) is NOT found in the sources:
- Explicitly state in the **SAME LANGUAGE** as the user's prompt (e.g., Arabic if asked in Arabic) that the required information was missing from the textbook sources.
- Vary your phrasing naturally each time.
- State clearly that you are providing the remaining answer from your general knowledge and recommend verifying it.
- Proceed to answer the question using your general knowledge, while clearly distinguishing which parts came from external knowledge vs. the sources.
- You should fully answer the question even if part of the answer is not from the sources 

-----------------------
SOURCES (May be irrelevant or None)
-----------------------

{sources}

-----------------------
CONVERSATION HISTORY
-----------------------

{chat_history}

-----------------------
STUDENT QUESTION
-----------------------

{user_query}

-----------------------
OUTPUT FORMAT
-----------------------
{output_format_txt}
- Format your response using Markdown.
- Use bolding for emphasis, bullet points or numbered lists for readability, and headers to organize sections.
- For data comparisons, use tables.
- Ensure the layout is visually structured and scannable

EDUCATIONAL RULES:
- Sound natural
- Provide clear and complete answers
- If the answer is not from the sources, don't write this, otherwise:
  You MUST refer to the sources at the end in bullet points IN THIS FORM:
  "Sources:
  • {{Subject}} - Unit {{unit_num}} - Lesson {{lesson_num}} - Page {{page_num}}"
  For example: "Sources:
  • Science - Unit 1 - Lesson 3 - Page 58 to 62"
  Do not include country or education type.

-----------------------

Now answer the student's question.
"""


class AddSource:
    def __init__(
        self,
        rag_service: RagService,
        mistral_api_key: str,
    ):
        self.rag_service = rag_service
        self.mistral_client: Mistral = Mistral(api_key=mistral_api_key)
        self.gemini_client = rag_service.gemini_client

    def prepare_pdf(self, pdf_bytes: bytes):
        """ """

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

        start = time.perf_counter()
        book_pdf = upload_pdf()
        print(f"PREPARE PDF — UPLOAD: {time.perf_counter() - start:.2f}s")

        # Create the system instructions
        system_instructions = """
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

Your task is to analyze ONLY the Main Book: the primary textbook containing the explanations and lessons intended to be learned.
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

## 4. Identify Explanation Page Ranges

Identify all ranges of digital pages within the Main Book that contain educational explanation/content that should be included in the learning platform.

An explanation page may contain:

- Explanations of concepts
- Definitions
- Examples
- Worked examples
- Educational diagrams or figures
- Explanatory tables
- Normal lesson content
- "Test Your Knowledge" sections or questions embedded WITHIN an explanation
- Q&A questions embedded WITHIN normal explanatory content

An explanation page must be inside a lesson. Do Not include explanation pages that are in between questions, rounds, or not in a lesson generally.

IMPORTANT: A page must NOT be excluded merely because it contains questions.
Exclude a page as non-explanation content ONLY when the page consists entirely, or essentially entirely, of questions, exercises, tests, homework, or similar assessment/practice material.

For example:
- A lesson explanation containing a small "Test Your Knowledge" section → INCLUDE the page.
- A lesson explanation containing some questions alongside explanatory content → INCLUDE the page.
- A page consisting entirely of exercises/questions → EXCLUDE the page.

An entirely-question-based page may occur in the middle of a lesson's explanation pages.

For example, if the same lesson has:
- explanation pages 10-15
- an all-question page 16
- explanation pages 17-22

you MUST return two separate ranges: 10-15 and 17-22.
Do NOT merge them into 10-22.
Also exclude other clearly non-explanatory material such as introductions, tables of contents,
indexes, advertisements, acknowledgements, publisher information, answer keys, revision-only material,
and other supplementary sections when they are not part of the Main Book's actual lesson explanations.

---

## 5. Determine Unit and Lesson Metadata

For every explanation-page range, determine:
- Unit number
- Unit name
- Lesson number
- Lesson name

The unit and lesson information should primarily be determined from the headers and/or footers of the Main Book pages, where this information is provided.
Preserve the names as they appear in the textbook.
Use surrounding pages when necessary to correctly determine which unit and lesson a range belongs to.
The metadata applies to every page within its corresponding explanation range.
If an all-question page splits a lesson into multiple explanation ranges, the ranges on both sides should retain the same lesson metadata when they belong to the same lesson.

IMPORTANT: Some explanation pages may cover TWO OR MORE lessons together. When a page or explanation-page range explicitly belongs to multiple lessons, include ALL applicable lesson numbers and lesson names in `lesson_num` and `lesson_name` as lists.

For example, if an explanation page covers "Lesson 1 & 2", return:
- lesson_num: [1, 2]
- lesson_name: ["Lesson 1 Name", "Lesson 2 Name"]

Do NOT create a combined lesson number or combined lesson name such as `"1 & 2"` or `"Lesson 1 & 2"`.
Each individual lesson must remain separately identifiable.

For normal explanation pages belonging to only one lesson, return `lesson_num` and `lesson_name` as a single value.

---

## 6. Page Ranges

All ranges MUST be expressed using digital/PDF page numbers.
`start_page` is the first digital page included in the explanation range.
`end_page` is the last digital page included in the explanation range.
Do not use printed page numbers for these fields.
Return ranges in ascending digital-page order.
Do not overlap ranges.
Do not include pages outside the Main Book.

---

## 7. Required Output

Return ONLY valid JSON matching exactly the structure in this example:

{
  "digital_to_actual_pages_offset": 4,
  "explanation_pages_ranges": [
    {
      "start_page": 5,
      "end_page": 12,
      "unit_name": "Thermal Energy",
      "unit_num": 1,
      "lesson_name": "Thermal and Chemical Changes",
      "lesson_num": 2
    },
    {
      "start_page": 13,
      "end_page": 26,
      "unit_name": "Thermal Energy",
      "unit_num": 1,
      "lesson_name": ["Lesson 1 Name", "Lesson 2 Name"],
      "lesson_num": [1, 2]
    }
  ]
}

The top-level object MUST contain exactly these two keys:

- `digital_to_actual_pages_offset`
- `explanation_pages_ranges`

Each item in `explanation_pages_ranges` MUST contain exactly these six keys:

- `start_page`
- `end_page`
- `unit_name`
- `unit_num`
- `lesson_name`
- `lesson_num`

Data types MUST be:

- `digital_to_actual_pages_offset`: integer
- `start_page`: integer
- `end_page`: integer
- `unit_name`: string
- `unit_num`: integer
- `lesson_name`: string OR list of strings
- `lesson_num`: integer OR list of integers

When an explanation range belongs to multiple lessons,
`lesson_name` and `lesson_num` MUST be lists containing all applicable lessons in their textbook order.

Do not wrap the JSON in Markdown code fences.
Do not include any additional keys.
Do not include any explanation before or after the JSON.
"""

        # Send the request to the Gemini API
        start = time.perf_counter()
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
                print(e)
                continue

        json_response = json.loads(response.text)
        print(f"PREPARE PDF — GEMINI REQUEST: {time.perf_counter() - start:.2f}s")

        # Prepare explanation-only PDF
        offset: int = json_response["digital_to_actual_pages_offset"]
        explanation_ranges: list = json_response["explanation_pages_ranges"]

        # Open the original PDF from its bytes
        source_pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        # Create the new explanation-only PDF, map its pages to the actual pages,
        # and create the metadata mapping dict by page
        prepared_pdf = pymupdf.open()
        digital_to_actual_mapping = {}
        pages_metadata = {}

        new_digital_page = 1

        for page_range in explanation_ranges:
            start_page = page_range["start_page"]
            end_page = page_range["end_page"]

            # Validate the range
            if start_page < 1 or end_page > len(source_pdf) or start_page > end_page:
                raise ValueError(
                    f"Invalid page range returned by Gemini: {start_page}-{end_page}. "
                    f"The PDF contains {len(source_pdf)} pages."
                )

            # Copy the entire range at once.
            # Gemini uses 1-based digital pages, while PyMuPDF uses 0-based indexes.
            prepared_pdf.insert_pdf(
                source_pdf,
                from_page=start_page - 1,
                to_page=end_page - 1,
            )

            # Map each new digital page to its actual page number + its metadata.
            for original_digital_page in range(start_page, end_page + 1):
                actual_page = original_digital_page + offset

                digital_to_actual_mapping[new_digital_page] = actual_page

                pages_metadata[actual_page] = {
                    "unit_name": page_range["unit_name"],
                    "unit_num": page_range["unit_num"],
                    "lesson_name": page_range["lesson_name"],
                    "lesson_num": page_range["lesson_num"],
                }

                new_digital_page += 1

        # Convert the prepared PDF back to bytes.
        explanations_pdf_bytes = prepared_pdf.tobytes()
        debug_pdf_path = "debug/prepared/explanations_only.pdf"

        os.makedirs(os.path.dirname(debug_pdf_path), exist_ok=True)

        with open(debug_pdf_path, "wb") as f:
            f.write(explanations_pdf_bytes)

        # Close the PDF documents.
        prepared_pdf.close()
        source_pdf.close()

        return explanations_pdf_bytes, digital_to_actual_mapping, pages_metadata

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

        # Get the b64 format from the PDF bytes
        pdf_data_url = "data:application/pdf;base64," + base64.b64encode(
            pdf_bytes
        ).decode("utf-8")

        response = self.mistral_client.ocr.process(
            model="mistral-ocr-latest",
            document={"type": "document_url", "document_url": pdf_data_url},
            # extract_footer=True,
        )

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

    def attach_metadata(
        self,
        ocr_result: list[dict],
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
        batch_id = str(uuid.uuid4())

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
                match = re.search(r"[.!?]\s+", text[end:])

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
    ):
        """
        Process a PDF book and add it to the vector database.

        The pipeline performs the following steps:
        1. OCR the PDF and extract page text.
        2. Attach subject, publisher, unit, and lesson metadata.
        3. Split each page into semantic chunks.
        4. Embed the chunks and upload them to the vector database.

        Parameters
        ----------
        pdf_bytes : bytes
            The raw bytes of the PDF document.
        grade : str
            The grade of the student.
        subject : str
            The subject of the book.
        book_publisher : str
            The publisher of the book.

        Returns
        -------
        None
        """

        print("PREPARING PDF")
        start = time.perf_counter()

        explanations_pdf_bytes, digital_to_actual_mapping, pages_metadata = (
            self.prepare_pdf(pdf_bytes)
        )

        print(f"PREPARING PDF FINISHED — {time.perf_counter() - start:.2f}s")

        print("STARTING OCR")
        start = time.perf_counter()

        pages = self.ocr_pdf(explanations_pdf_bytes, digital_to_actual_mapping)

        print(f"OCR FINISHED — {time.perf_counter() - start:.2f}s")

        start = time.perf_counter()

        pages = self.attach_metadata(
            pages,
            unit_lesson_metadata=pages_metadata,
            grade=grade,
            subject=subject,
            book_publisher=book_publisher,
            term=1,
        )

        print(f"METADATA ATTACHED — {time.perf_counter() - start:.2f}s")

        start = time.perf_counter()

        chunks = self.chunk_pages(pages)

        print(f"CHUNKED — {time.perf_counter() - start:.2f}s")

        start = time.perf_counter()

        self.insert_to_vector_db(chunks)

        print(f"INSERTED TO VECTOR DB — {time.perf_counter() - start:.2f}s")

    @staticmethod
    def current_term():
        month = datetime.now().month

        if 9 <= month <= 12 or month == 1:
            return 1
        elif 2 <= month <= 5:
            return 2
        else:
            return 1
