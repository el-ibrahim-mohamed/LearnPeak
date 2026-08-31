from google.genai import Client, types
import mimetypes
import json
from firebase_admin.db import Reference
import time
import uuid
from config import GEMINI_LITE_FIRST


class QuizzesService:
    """Quiz generation and correction"""

    def __init__(self, gemini_client: Client):
        self.client = gemini_client

    def generate_quiz(
        self,
        title: str,
        number_of_questions: int,
        difficulty: str,
        description: str = "",
        book_text: str = "",
        text: str = "",
        audios: list[dict] = [],
        videos: list[dict] = [],
        youtube_videos_urls: list[str] = [],
        files: list[dict] = [],
        web_urls: list[str] = [],
        custom_instructions: str = "",
    ):
        """"""
        
        title = title.strip()
        description = description.strip()
        book_text = book_text.strip()
        text = text.strip()
        custom_instructions = custom_instructions.strip()

        # --- 1. Build the main prompt ---
        prompt = f"""You are a quiz generator tool for students.

========================

Quiz Information:
Title: {title}
{f"Description: {description}" if description else ""}
Number of Questions: {number_of_questions}
Difficulty: {difficulty}

========================

Question Types to Include:
1. Multiple Choice Questions (MCQ) - 4 choices each (majority)
2. True or False questions (some)
3. Fill in the Blank questions (a few)

========================

Source Rules:

You may receive two categories of sources:

1. BOOK SOURCE
This is content taken directly from the student's selected curriculum textbook.
Treat it as the primary curriculum source.

2. EXTERNAL SOURCES
These are additional materials provided by the user, such as text, audio,
video, YouTube videos, files, or websites.

Use the available sources to create accurate questions.
Do not invent facts that are not supported by the provided sources.

If both BOOK SOURCE and EXTERNAL SOURCES are available, use both.
Prioritize the BOOK SOURCE when the sources conflict because it represents
the student's curriculum textbook.

========================

Your Task:
Generate only the quiz questions with answers and provide your response like this sample JSON format:

{{
    "quiz_questions": {{
        "q1": {{
            "type": "mcq",
            "question": "What is the main function of mitochondria?",
            "choices": [
                "Energy production",
                "Protein synthesis",
                "DNA replication",
                "Waste removal"
            ],
            "correct_answer": "Energy production"
        }},
        "q2": {{
            "type": "true_or_false",
            "question": "Photosynthesis occurs in animal cells.",
            "correct_answer": "False"
        }},
        "q3": {{
            "type": "fill_in_the_blank",
            "question": "The process of cell division is called _____.",
            "correct_answer": "mitosis"
        }}
    }}
}}

Important:
- Generate exactly {number_of_questions} questions.
- MCQs must have exactly 4 choices.
- The correct answer must exactly match one of the choices for MCQs.
- True/False answers must be exactly "True" or "False".
- Fill-in-the-blank answers should be concise.
- Do not include quiz information in the JSON response.
- Do not include explanations outside the requested JSON structure.
"""

        if custom_instructions:
            prompt += f"""
            ========================

            Custom instructions from the user:
            {custom_instructions}
            """

        # --- 2. Add BOOK SOURCE ---
        if book_text:
            prompt += f"""
            ========================

            BOOK SOURCE:
            The following content was retrieved from the student's curriculum textbook.

            {book_text}
            """

        # --- 3. Add EXTERNAL SOURCES ---
        external_text_sources = []

        if text:
            external_text_sources.append(f"TEXT SOURCE:\n{text}")

        if youtube_videos_urls:
            youtube_text = "YOUTUBE VIDEO URLS:\n"
            youtube_text += "\n".join(youtube_videos_urls)
            external_text_sources.append(youtube_text)

        if web_urls:
            website_text = "WEBSITE URLS:\n"
            website_text += "\n".join(web_urls)
            external_text_sources.append(website_text)

        if external_text_sources:
            prompt += """
            ========================

            EXTERNAL SOURCES:

            """ + "\n\n".join(external_text_sources)

        # Build the final contents only AFTER the prompt is complete.
        contents = [prompt]

        # --- 4. Add binary external sources ---
        for audio in audios:
            mime_type, _ = mimetypes.guess_type(audio["name"])
            contents.append(
                types.Part.from_bytes(
                    data=audio["bytes"],
                    mime_type=mime_type,
                )
            )

        for video in videos:
            mime_type, _ = mimetypes.guess_type(video["name"])
            contents.append(
                types.Part.from_bytes(
                    data=video["bytes"],
                    mime_type=mime_type,
                )
            )

        for file in files:
            mime_type, _ = mimetypes.guess_type(file["name"])
            contents.append(
                types.Part.from_bytes(
                    data=file["bytes"],
                    mime_type=mime_type,
                )
            )

        # --- 5. Generate quiz ---
        response = None

        for model in GEMINI_LITE_FIRST:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config={
                        "response_mime_type": "application/json",
                    },
                )
                break
            except Exception as e:
                print(e)
                continue

        if response is None:
            raise RuntimeError("Failed to generate quiz with all available models.")

        return json.loads(response.text)["quiz_questions"]

    def grade_quiz(self, quiz_questions: dict, answers: list) -> dict:
        graded_questions = {}
        incorrect_questions = {}

        for id, answer in zip(quiz_questions, answers):
            if answer == quiz_questions[id]["correct_answer"]:
                graded_questions[id] = True
            else:
                incorrect_questions[id] = {
                    "question": quiz_questions[id]["question"],
                    "correct_answer": quiz_questions[id]["correct_answer"],
                }

        prompt = f"""You are a quiz grading tool.
Here are the incorrect answers of the user in the form of a dict:
{incorrect_questions}

Your Task:
Provide a review on each wrong answer with:
1. explaining the correct answer
2. explaining why the user's answer is wrong not roughly (if there was an answer)
3. bolding the exact correct answer (markdown)
The review should be brief in 1-3 lines.

Your output should be in a JSON structure like this sample:
{{
    "q3": "Your review here",
    "q7": "Your review here",
    ...
}}
"""

        for model in GEMINI_LITE_FIRST:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=[prompt],
                    config={"response_mime_type": "application/json"},
                )
            except:
                continue

        quiz_grading = json.loads(response.text)

        # Adding the wrong answers' reviews to the graded_questions dict
        for id in quiz_grading:
            graded_questions[id] = quiz_grading[id]

        return graded_questions


class QuizzesHistory:
    def __init__(self, root_ref: Reference):
        self.root_ref = root_ref

    def save_quiz(
        self,
        user_uid: str,
        quiz_info: dict,
        quiz_questions: dict,
    ) -> str:
        quiz_id = str(uuid.uuid4())

        quizzes_ref = self.root_ref.child(
            f"users/{user_uid}/history/quizzes"
        )

        quiz_saving_data = {
            "id": quiz_id,
            "created_at": time.time(),
            "quiz_info": quiz_info,
            "quiz_questions": quiz_questions,
        }

        quizzes_ref.child(quiz_id).set(quiz_saving_data)

        return quiz_id

    def save_quiz_grading(
        self,
        user_uid: str,
        quiz_id: str,
        grading_data: dict,
    ) -> str:
        grading_id = str(uuid.uuid4())

        gradings_ref = self.root_ref.child(
            f"users/{user_uid}/history/quizzes/{quiz_id}/submit_gradings"
        )

        grading_saving_data = {
            "id": grading_id,
            "grading_data": grading_data,
            "created_at": time.time(),
        }

        gradings_ref.child(grading_id).set(grading_saving_data)

        return grading_id

    def get_saved_quizzes(self, user_uid: str) -> list[dict]:
        quizzes_ref = self.root_ref.child(
            f"users/{user_uid}/history/quizzes"
        )

        quizzes_dict: dict = quizzes_ref.get()

        quizzes = []

        if quizzes_dict:
            for quiz_id, quiz in quizzes_dict.items():
                quizzes.append({
                    "id": quiz_id,
                    **quiz,
                })

            quizzes.sort(
                key=lambda x: x.get("created_at", 0),
                reverse=True,
            )

        return quizzes

    def delete_quiz(
        self,
        user_uid: str,
        quiz_id: str,
    ):
        self.root_ref.child(
            f"users/{user_uid}/history/quizzes/{quiz_id}"
        ).delete()

