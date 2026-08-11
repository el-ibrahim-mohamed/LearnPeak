from typing import Literal, List, Dict, Optional
from google import genai
from google.genai import types
import json
import uuid
import re
from datetime import datetime
import base64
from mistralai.client import Mistral
from qdrant_client.models import (
    Filter,
    PointStruct,
    FieldCondition,
    MatchValue,
    MatchAny,
)
from services.rag.embedding_service import EmbeddingService
from services.rag.qdrant_service import QdrantService


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
    # AI Mode Methods
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

        # Metadata fields used to identify a lesson
        metadata_keys = ["country", "education", "subject", "unit_num", "lesson_num"]

        # Page retrieval also requires the page number
        if scope == "page":
            metadata_keys.append("page_num")

        # Collect the unique page/lesson combinations
        combinations = {
            tuple(payload[key] for key in metadata_keys)
            for payload in chunks_payloads
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

    def generate_response(
        self, user_query, sources: str, chat_history=[], get_chat_title=True
    ):
        prompt = self.ai_prompt(
            user_query, sources, chat_history, get_chat_title, output_format="json"
        )

        for model in [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-3.1-flash",
            "gemini-2.5-flash",
        ]:
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

        for model in [
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-3.1-flash",
            "gemini-2.5-flash",
        ]:
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
{{
    "response": "Markdown formatted answer...",
    "suggested_chat_title": "Suggest a chat title based on the first prompt..."
    ],

}}

"response":"""

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

If the whole answer or part of it is not found in the sources: 
- Say "The provided sources do not contain information regarding {{...}}.
  I will provide the answer from my general knowledge, and you may want to independently verify it." OR SIMILAR
  Then answer from your knowledge.
- When answering any part from outside the sources, you MUST declare that it is not found in the sources.
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

    def ocr_pdf(self, pdf_bytes: bytes) -> list[dict]:
        """
        Perform OCR on a PDF document using Mistral OCR and extract the text of each page.

        The PDF is sent to the Mistral OCR API directly from its bytes. For each page,
        the function extracts the page's Markdown content and footer, determines the
        real page number from the footer, and returns a list containing the page number
        and its corresponding OCR text.

        Parameters
        ----------
        pdf_bytes : bytes
            The raw bytes of the PDF document to process.

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
            extract_footer=True,
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
            footer_text = page.footer

            page_num = extract_page_number(footer_text)

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
        grade: str,
        subject: str,
        unit_lesson_input: str,
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

        # Map each page number to its metadata
        page_map = {}

        for line in unit_lesson_input.splitlines():
            if not line.strip():
                continue

            page_range, metadata = line.split(":", maxsplit=1)

            start_page, end_page = map(int, page_range.split("-"))

            unit_num, unit_name, lesson_num, lesson_name = [
                part.strip() for part in metadata.split(",", maxsplit=3)
            ]

            unit_num = int(unit_num.removeprefix("U"))
            lesson_num = int(lesson_num.removeprefix("L"))

            for page in range(start_page, end_page + 1):
                page_map[page] = {
                    "unit_num": unit_num,
                    "unit_name": unit_name,
                    "lesson_num": lesson_num,
                    "lesson_name": lesson_name,
                }

        # Attach metadata to each OCR page
        for page_data in ocr_result:
            unit_lesson_metadata = page_map.get(page_data["page_num"])

            page_data.update(
                {
                    "country": country,
                    "education": education,
                    "grade": grade,
                    "term": term,
                    "subject": subject,
                    "book_publisher": book_publisher,
                    **unit_lesson_metadata,
                }
            )

        return ocr_result

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
        unit_lesson_input: str,
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
        subject : str
            The subject of the book.
        book_publisher : str
            The publisher of the book.
        unit_lesson_input : str
            The page-to-unit/lesson mapping entered by the user.

        Returns
        -------
        None
        """

        print("STARTING OCR")
        pages = self.ocr_pdf(pdf_bytes)
        print("OCR FINISHED")

        pages = self.attach_metadata(
            pages,
            grade=grade,
            subject=subject,
            book_publisher=book_publisher,
            unit_lesson_input=unit_lesson_input,
            term=1,
        )
        print("METADATA ATTACHED")

        chunks = self.chunk_pages(pages)
        print("CHUNKED")

        self.insert_to_vector_db(chunks)

    @staticmethod
    def current_term():
        month = datetime.now().month

        if 9 <= month <= 12 or month == 1:
            return 1
        elif 2 <= month <= 5:
            return 2
        else:
            return 1
