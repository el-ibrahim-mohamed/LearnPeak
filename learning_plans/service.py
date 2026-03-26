from google.genai import Client
from ar.service import ARService
import json
import uuid


class LearningPlansService:
    def __init__(self, gemini_client: Client):
        self.client = gemini_client

    def generate_learning_plan(
        self,
        title: str,
        age: int,
        days_num: int,
        description: str = None,
        flashcards_num: int = 5,
        ar: bool = True,
        use_model_viewer: bool = False,
        sketchfab_api_key: str = "",
        github_username: str = "",
        github_access_token: str = "",
        repo: str = "",
    ):
        lp_prompt = f"""You are an AI Assistant in an educational platform.
Plan Info:
Title: {title}
User's Age: {age}
Number of Days: {days_num}
{f"Description (more details): {description}" if description else ""}

Your Task: Generate a learning plan of {days_num} days where each day, you generate this material about the topic:
1. Text Content
2. Youtube Video Embed URL (better to be relevant to the generated text)
3. {flashcards_num} Flashcards each with front (question/term), back (answer/definition), and hint (small clue)
4. Quiz on the given material with:
- Multiple Choice Questions (MCQ) - 4 choices each (majority)
- True or False questions (some)
- Fill in the Blank questions (a few)

You must return your response in a JSON structure like this:
{{
    "learning_plan": {{
        "days": [
            "day1": {{
                "text": "Text Content Here",
                "video": "Youtube Video Embed URL Here",
                "flashcards": [
                    {{"front": "Front Question/Term Here", "back": "Answer/Definition Here", "hint": "A small clue to the answer"}}, ...
                ],
                "quiz": {{
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
            }},
            ...
        ]
    }}
}}

Strict Note: You must only return the required points in this JSON, no more explainations."""

        response = self.client.models.generate_content(
            contents=[lp_prompt],
            model="gemini-2.5-flash",
            config={"response_mime_type": "application/json"},
        )

        json_response = json.loads(response.text)

        # Adding an ID and the metadata
        json_response["learning_plan"]["id"] = str(uuid.uuid4())
        json_response["learning_plan"]["title"] = title

        yield {
            "step": "lp",
            "lp": json_response["learning_plan"],
        }

        # AR Generation
        if ar:
            ar_service = ARService(
                sketchfab_api_key,
                github_username,
                github_access_token,
                repo,
                self.client,
            )

            for result in ar_service.generate_ar_experience(title, use_model_viewer):
                if result["step"] == "embed_and_description":
                    yield {
                        "step": "ar",
                        "sketchfab_embed_html": result["sketchfab_embed_html"],
                        "ai_description": result["ai_description"],
                    }
                    break

    @staticmethod
    def youtube_embed_html(embed_url: str) -> str:
        return f"""<iframe width="853" height="480" src="{embed_url}" frameborder="0"
allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
allowfullscreen>
</iframe>"""
