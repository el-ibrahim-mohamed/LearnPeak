from google.genai import Client, types
import mimetypes
import json


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
        text: str = "",
        audios: list[dict] = [],
        videos: list[dict] = [],
        youtube_videos_urls: list[str] = [],
        files: list[dict] = [],
        web_urls: list[str] = [],
        custom_instructions: str = "",
    ):
        text = text.strip()
        description = description.strip()

        # --- 1. Build the prompt ---
        prompt = f"""You are a quiz generator tool for students.

========================

Quiz Information:
Title: {title} {f"\nDescription: {description}" if description else ""}
Number of Questions: {number_of_questions}
Difficulty: {difficulty}

========================

Question Types to Include:
1. Multiple Choice Questions (MCQ) - 4 choices each (majority)
2. True or False questions (some)
3. Fill in the Blank questions (a few)

========================

Your Task:
Generate only the quiz questions with answers and provide your response like this sample JSON format:
{{
    "quiz_questions": {{
        "q1": {{
            "type": "mcq",
            "question": "What is the main function of mitochondria?",
            "choices": ["Energy production", "Protein synthesis", "DNA replication", "Waste removal"],
            "correct_answer": "Energy production"  # case-sensetive
        }},
        "q2": {{
            "type": "true_or_false",
            "question": "Photosynthesis occurs in animal cells.",
            "correct_answer": "False"  # capitalized, str not bool
        }},
        "q3": {{
            "type": "fill_in_the_blank",
            "question": "The process of cell division is called _____.",
            "correct_answer": "mitosis"
        }},
        ...
    }}
}}
Note: You mustn't include other quiz info like the title or difficulty in you JSON response.

========================

{f"Custom instructions from the user:\n{custom_instructions}\n\n========================" if custom_instructions else ""}

{"Sources to base questions on:" if any([text, audios, videos, files, web_urls]) else "The sources are open."}"""

        # --- 2. Add sources conditionally ---
        contents = [prompt]

        if text:
            prompt += f"\n**Text Source:**\n{text}"

        if youtube_videos_urls:
            youtube_videos_urls_str = "\nYouTube Video URLs:"
            for url in youtube_videos_urls:
                youtube_videos_urls_str += f"\n{url}"
            prompt += youtube_videos_urls_str

        if web_urls:
            web_urls_str = "\nWebsite URLs:"
            for url in web_urls:
                web_urls_str += f"\n{url}"
            prompt += web_urls_str

        if audios:
            for audio in audios:
                mime_type, _ = mimetypes.guess_type(audio["name"])
                contents.append(
                    types.Part.from_bytes(data=audio["bytes"], mime_type=mime_type)
                )

        if videos:
            for video in videos:
                mime_type, _ = mimetypes.guess_type(video["name"])
                contents.append(
                    types.Part.from_bytes(data=video["bytes"], mime_type=mime_type)
                )

        if files:
            for file in files:
                mime_type, _ = mimetypes.guess_type(file["name"])
                contents.append(
                    types.Part.from_bytes(data=file["bytes"], mime_type=mime_type)
                )

        for model in [
            "gemini-3.1-flash-lite-preview",
            "gemini-2.5-flash-lite",
            "gemini-3.1-flash-preview",
            "gemini-2.5-flash",
        ]:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config={"response_mime_type": "application/json"},
                )
            except:
                continue

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

        for model in [
            "gemini-3.1-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]:
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
