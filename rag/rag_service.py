from typing import List, Dict, Optional, Any
from PIL import Image
import pytesseract
import fitz
from google import genai
from google.genai import types
import json
import uuid
import re
from io import BytesIO
from datetime import datetime
from itertools import chain
from qdrant_client import models
from rag.embedding_service import EmbeddingService
from rag.qdrant_service import QdrantService


class RagService:
    """
    Business logic layer for handling Q&A vector storage and retrieval.
    """

    def __init__(
        self, qdrant_service: QdrantService, embedding_service: EmbeddingService
    ):
        self.qdrant_service = qdrant_service
        self.qdrant_client = qdrant_service.get_client()
        self.collection_name = qdrant_service.collection_name
        self.embedding_service = embedding_service

    # -------------------------
    # Insert Methods
    # -------------------------

    def insert_batch(
        self,
        embed_texts: List[str],
        point_ids: List[str],
        payloads: List[dict],
    ) -> None:

        # Batch embedding (single model call)
        embeddings = self.embedding_service.embed_batch(embed_texts)

        points = [
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )
            for point_id, payload, embedding in zip(point_ids, payloads, embeddings)
        ]

        if points:
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
        score_threshold: float = 0.5,
        query_filter: Optional[models.Filter] = None,
    ) -> List[Dict]:
        """
        Takes raw user question string, encodes internally, returns list of payload dicts.
        """

        query_embedding = self.embedding_service.embed_text(user_question)

        response = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

        results = response.points

        return [res.payload for res in results] if results else []


class AddSource:

    def __init__(
        self,
        gemini_client: genai.Client,
        rag_service: RagService,
        grade: str,
        country: str = "egypt",
        education: str = "national",
        term: int = None,
    ):
        if not term:
            term = self.current_term()

        self.gemini_client = gemini_client
        self.rag_service = rag_service
        self.country = country
        self.education = education
        self.grade = grade
        self.term = term

    def ocr_pdf(self, pdf_path: str) -> list[dict]:
        doc = fitz.open(pdf_path)
        pages_text = []

        for i in range(len(doc)):
            page = doc[i]

            digital_text = page.get_text()

            if digital_text:
                pages_text.append(digital_text)
            else:
                pix = page.get_pixmap(dpi=400)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img)

                pages_text.append(text)

        return pages_text

    def slice_pdf(
        self,
        pdf_bytes: bytes,
        tokens_per_page: int = 1800,
        model_output_limit: int = 65536,
        safety_margin: int = 10000,
    ) -> list[bytes]:
        safe_limit = model_output_limit - safety_margin
        max_pages_per_chunk = safe_limit // tokens_per_page

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        chunks = []
        for i, start in enumerate(range(0, total_pages, max_pages_per_chunk)):

            end = min(start + max_pages_per_chunk, total_pages)

            chunk_doc = fitz.open()
            chunk_doc.insert_pdf(doc, from_page=start, to_page=end - 1)

            chunk_bytes = chunk_doc.tobytes()
            chunks.append(chunk_bytes)

        return chunks

    def generate_questions(
        self,
        questions_pdf_bytes: bytes,
        answers_pdf_bytes: bytes,
        gemini_model: str = "gemini-3.1-flash-lite-preview",
    ):
        prompt, system_instructions = self.construct_prompt()

        uploaded_questions = self.gemini_client.files.upload(
            file=BytesIO(questions_pdf_bytes),
            config={
                "mime_type": "application/pdf",
                "display_name": "Explanations and Questions PDF",
            },
        )

        uploaded_answers = self.gemini_client.files.upload(
            file=BytesIO(answers_pdf_bytes),
            config={"mime_type": "application/pdf", "display_name": "Model Answer PDF"},
        )

        response = self.gemini_client.models.generate_content(
            model=gemini_model,
            contents=[prompt, uploaded_questions, uploaded_answers],
            config=types.GenerateContentConfig(
                system_instruction=system_instructions,
                response_mime_type="application/json",
                max_output_tokens=64000,
                temperature=0.1,
            ),
        )

        print(f"Finish Reason: {response.candidates[0].finish_reason}")
        json_results = json.loads(response.text)

        # DEBUG SAVE
        debug_file = f"debug/gemini_response_{uuid.uuid4().hex}.json"
        with open(debug_file, "w", encoding="utf-8") as f:
            json.dump(json_results, f, indent=4)

        return json_results

    def attach_metadata(
        self,
        gemini_output: Dict[str, Any],
        subject: str,
        book_publisher: str,
        start_ex_num: int = 0,
    ) -> list[Dict[str, Any]]:

        points_payloads = []

        for unit_obj in gemini_output.get("units", []):
            unit_obj: dict
            unit_num = unit_obj.get("unit_num")
            unit_name = unit_obj.get("unit_name")

            for lesson_obj in unit_obj.get("lessons", []):
                lesson_obj: dict
                lesson_num = lesson_obj.get("lesson_num")
                lesson_name = lesson_obj.get("lesson_name")

                prev_ex_title = None
                q_num_counter = 0
                ex_num_counter = start_ex_num
                ex_reset_page = []  # Manual

                for page_obj in lesson_obj.get("pages", []):
                    page_obj: dict
                    page: int = page_obj.get("page")

                    # Reset ex_num_counter when it is the questions first page
                    if page in ex_reset_page:
                        ex_num_counter = 0

                    explanations_list = page_obj.get("explanation", [])
                    questions_list = page_obj.get("questions", [])

                    # Deleting questions in between explanations to prevent messing the counters
                    if explanations_list and questions_list:
                        questions_list = []

                    lesson_id = (
                        f"{self.country}_{self.education}_{self.grade}_term{self.term}_"
                        f"{subject}_unit{unit_num}_lesson{lesson_num}".lower().replace(
                            " ", "_"
                        )
                    )

                    default_payload = {
                        "country": self.country,
                        "education": self.education,
                        "grade": self.grade,
                        "term": self.term,
                        "book_publisher": book_publisher,
                        "subject": subject,
                        "unit_num": unit_num,
                        "unit_name": unit_name,
                        "lesson_num": lesson_num,
                        "lesson_name": lesson_name,
                        "lesson_id": lesson_id,
                        "page": page,
                    }

                    if explanations_list:
                        for i, exp_chunk in enumerate(explanations_list):
                            chunk_txt = (
                                f"[Unit {unit_num} Lesson {lesson_num}]\n{exp_chunk}"
                            )

                            unique_string = f"{lesson_id}|{page}|chunk{i + 1}|{chunk_txt}"
                            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

                            explanation_point = {
                                **default_payload,
                                "id": chunk_id,
                                "point_type": "explanation",
                                "chunk_txt": chunk_txt,
                            }
                            points_payloads.append(explanation_point)

                    for q in questions_list:
                        q: dict

                        ex_title: str = q.get("ex_title", "").strip()
                        ex_type: str = q.get("type", "text")
                        q_txt: str = q.get("q_txt", "").strip()

                        # Constructing q_num & ex_num ← UPDATED
                        normalized_title = ex_title.lower()
                        if normalized_title != prev_ex_title:
                            q_num_counter = 1
                            ex_num_counter += 1
                            prev_ex_title = normalized_title
                        else:
                            q_num_counter += 1

                        # Skip diagram questions but still "count" the number
                        check_text = f"{ex_title} {q_txt}".lower()
                        diagram_keywords = [
                            "diagram",
                            "figure",
                            "graph",
                        ]

                        if any(w in check_text for w in diagram_keywords):
                            continue

                        # Filter out question num
                        q_txt = re.sub(r"^\(?\d+\)?[.)]?\s*", "", q_txt).strip()

                        # Add the checkmark and the ✗ in ex_title
                        if ex_type in ["true_false", "true_false_with_correction"]:
                            ex_title = (
                                ex_title.replace("(T)", "(✓)")
                                .replace("(t)", "(✓)")
                                .replace("()", "Put (✓)")
                                .replace("(X)", "(✗)")
                                .replace("(x)", "(✗)")
                            )

                        ex_title.rstrip(":")

                        # Deterministic UUID
                        unique_string = f"{lesson_id}|{page}|{q_num_counter}|{q_txt}"
                        question_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

                        question_point = {
                            **default_payload,
                            "point_type": "question",
                            "id": question_id,
                            "ex_title": ex_title,
                            "ex_type": ex_type,
                            "ex_num": ex_num_counter,
                            "q_num": q_num_counter,
                            "q_txt": q_txt,
                            "a_txt": q.get("a_txt"),
                            "mcq_choices": q.get("mcq_choices"),
                        }

                        points_payloads.append(question_point)

        return points_payloads

    def insert_to_db(self, points: list[dict]):
        embed_texts = []
        point_ids = []
        payloads = []

        for p in points:
            embed_text = p["q_txt"] if p["point_type"] == "question" else p["chunk_txt"]
            embed_texts.append(embed_text)
            point_ids.append(p["id"])
            payloads.append(p)

        self.rag_service.insert_batch(embed_texts, point_ids, payloads)

    def add_book(
        self,
        subject: str,
        book_publisher: str,
        questions_pdf_bytes: bytes,
        answers_pdf_bytes: bytes,
        gemini_model: str = "gemini-3.1-flash-lite-preview",
    ):
        # Slice the large PDF to fit the model output tokens limit
        question_chunks = self.slice_pdf(questions_pdf_bytes)

        all_results = []
        for q_chunk in question_chunks:
            result = self.generate_questions(q_chunk, answers_pdf_bytes, gemini_model)
            all_results.append(result)

        # Attach metadata to each question and explanation chunk
        points_payloads = []
        for result in all_results:
            point = self.attach_metadata(result, subject, book_publisher)
            points_payloads.append(point)

        points_payloads = list(chain.from_iterable(points_payloads))

        with open("enriched_questions.json", "w") as f:
            json.dump(points_payloads, f, indent=4)

        # self.insert_to_db(questions_payloads)

    @staticmethod
    def construct_prompt():
        system_instructions = """
### ROLE
You are an Expert Educational Data Extraction Engine. Your goal is to convert PDF textbooks into structured RAG-ready JSON.

### TASK
1. Analyze 'Explanation and Questions PDF' and 'Model Answer PDF'.
2. For explanation pages, perform OCR or text extraction to extract 100% of the text in the pages.
   Handle layouts, tables, containers, colors, etc. You should chunk the whole extracted text of the page into chunks.
3. For questions pages, match every question from the questions PDF to its exact answer in the answers PDF.
4. Extract 100% of the texts. Do not summarize, edit, or skip texts.

### EXPLANATION CHUNKING RULES
1. SEMANTIC BOUNDARIES: Preserve a little context in the chunks. Do not break in the middle of a sentence.
2. SEMANTIC ORDER: Chunks MUST be in the list in the same order they appear.
3. TOKEN LIMIT: Each chunk must be approximately 30-120 words, up to 150 tokens (to fit the 200 token limit of the embedding model).
4. IMAGE DESCRIPTION: If a chunk refers to a diagram or table, include a brief text description of that visual within the chunk text (1-2 sentences).

### OUTPUT SCHEMA
You MUST return JSON object with this structure:
{
    "units": [  # All the units of the whole book in this list
        {
            "unit_num": 1,
            "unit_name": "Unit Name here...",
            "lessons": [  # All the lessons of unit 1 in this list
                {
                    "lesson_num": 1,
                    "lesson_name": "Lesson Name here...",
                    "pages": [
                        {
                            "page": 18,  # The number of the page in the BOOK (not the PDF)

                            # If the page is an explanation page
                            "explanation": [
                                "The explanation text of chunk 1 here...",
                                "The explanation text of chunk 2 here...",
                                ...
                            ]

                            # If the page is a questions page
                            "questions": [  # All the questions of this page in this list
                                {
                                    "ex_title": "e.g. Write the scientific term",
                                    "type": "text",
                                    "q_txt": "Question text here...",
                                    "a_txt": "The answer to the question here...",  
                                    "mcq_choices": ["Choice a text", "Choice b text", ...] | null  # Only with mcq questions, null otherwise
                                },
                                # The same JSON for every question
                            ]
                        }
                    ]
                },
                # The same JSON for every lesson
                {
                    "lesson": 2,
                    "pages": [...]
                }
            ]
        },
        # The same JSON for every unit
        {
            "unit": 2,
            "lessons": [...]
        }
    ]
}

### EXTRACTION RULES
- TYPE 'mcq': 'a_txt' must be the INTEGER index of the correct choice. For example, (0=a, 1=b, 2=c, 3=d)
- TYPE 'complete': Represent blanks as '_____'. 'a_txt' is a LIST of strings of the answers respectively.
- TYPE 'true_false': 'a_txt' is a STRING ('True' or 'False').
- TYPE 'true_false_with_correction': 'a_txt' is a LIST ["True", null] or
  ["False", {"mistake": "The exact text of the mistake part in q_txt", "correction": "Correction text"}].
- TYPE 'correct_underlined': 'a_txt' is a DICT {"mistake":"The exact text of the mistake part in q_txt", "correction":"Correction text"}
- TYPE 'text': Standard Q&A.
- NO metadata in 'q_txt': Strip exercise titles and question numbers (e.g., "(2)").
- Replace checkmarks with 'T' in "true_false" or "true_false_with_correction" exercise titles.
- You mustn't stack all the questions of one exercise in a single JSON object, every question should have one.
NOTE: Any Questions in between explanation pages should NOT be added to the questions list, but rather, in the explanation text.

### CRITICAL ADHERENCE
- Return ONLY valid JSON, do not include explanations, comments, or markdown.
- Ensure JSON is valid.
- Questions inside the JSON must be in order as the book.
- Do NOT skip any single questions found in the PDF.
"""

        prompt = f"""You are an Expert Educational Data Extraction Engine.
Your goal is to convert PDF textbooks into structured RAG-ready JSON.

You will be provided these documents:
- A PDF of the Lesson Explanations and Questions in the book.
- A PDF of the corresponding Model Answer of the questions.

Your Task:
- Match ALL the question from the questions PDF with its corresponding answer in the answers PDF.
"""

        return prompt, system_instructions

    @staticmethod
    def estimate_tokens(text: str) -> int:
        # Rough estimation
        return len(text) // 4

    @staticmethod
    def current_term():
        month = datetime.now().month

        if 9 <= month <= 12 or month == 1:
            return 1
        elif 2 <= month <= 5:
            return 2
        else:
            return 2
