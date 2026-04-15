import requests
import mimetypes
from google.genai import Client, types
import string
import random
import base64
import json
from .errors import *


class ARService:
    """AR generation and explanation."""

    def __init__(
        self,
        sketchfab_api_key: str = "",
        github_username: str = "",
        github_access_token: str = "",
        repo: str = "",
        gemini_client: Client = None,
    ):
        self.sketchfab_api_key = sketchfab_api_key
        self.authorization_header = {"Authorization": f"Token {self.sketchfab_api_key}"}
        self.github_username = github_username
        self.github_access_token = github_access_token
        self.repo = repo
        self.gemini_client = gemini_client
        self._topic_name = ""

    @property
    def topic_name(self):
        """Get topic name with validation"""
        if not self._topic_name:
            raise ValueError(
                "Topic name is not set. Call set_topic() or pass it to generate_ar_experience()"
            )
        return self._topic_name

    @topic_name.setter
    def topic_name(self, value: str):
        """Set topic name with cleaning"""
        if not value or not value.strip():
            raise ValueError("Topic name cannot be empty.")
        self._topic_name = value.strip().lower()

    def search_models(self, quantity: int = 20) -> list:
        sketchfab_search_endpoint = "https://api.sketchfab.com/v3/search"
        params = {
            "q": self.topic_name,
            "type": "models",
            "downloadable": True,
            "count": quantity,
        }

        response = requests.get(
            sketchfab_search_endpoint, headers=self.authorization_header, params=params
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise SketchfabAuthError(
                    "Invalid Sketchfab API token. Check your credentials."
                ) from e
            raise SketchfabError("Failed to search models on Sketchfab.") from e

        return response.json()["results"]

    def best_model_and_ai_description(self, models: list) -> tuple[str, bytes, str]:
        """
        Analyzes multiple images with the Gemini API, allowing you to name them.

        Args:
            images: A list of dictionaries, where each dict has 'bytes', 'mime_type', and 'name'.
            text_prompt: The text to accompany the images.

        Returns:
            str:
            The uid of the chosen model on Sketchfab.
        """

        # --- 1. Getting images urls, titles, descriptions from the models ---
        images_urls = []
        titles = []
        descriptions = []
        for model in models:
            images_urls.append(model["thumbnails"]["images"][1]["url"])
            titles.append(model["name"])
            descriptions.append(model["description"])

        # --- 2. Creating the images contents ---
        images_bytes = []
        images_mime_types = []

        for image_url in images_urls:
            try:
                # Getting the image bytes
                response = requests.get(image_url)
                images_bytes.append(response.content)

                # Getting the image mime type
                mime_type, _ = mimetypes.guess_type(image_url)
                images_mime_types.append(mime_type)

            except requests.RequestException as e:
                raise SketchfabDownloadError(
                    "Failed to download one or more model thumbnails."
                ) from e

        # Creating the image data
        images = [
            {"bytes": image_bytes, "mime_type": mime_type, "name": f"image_{i}"}
            for i, (image_bytes, mime_type) in enumerate(
                zip(images_bytes, images_mime_types)
            )
        ]

        # --- 3. Creating the Prompt ---
        models_metadata = ""

        for i, (title, description) in enumerate(zip(titles, descriptions)):
            models_metadata += f"""[image_{i}]
Title: {title}
Description: {description}
"""

        prompt = f"""You are an AI assistant in an educational platform.
Your goal is to help students get and understand 3D models.
You have 2 tasks:

**Task1**
Analyze the following images, which are thumbnails of different 3D models.
Your task is to determine which image (3D model) best represents the topic: "{self.topic_name}".

Evaluation criteria:
1. Relevance to the topic "{self.topic_name}" in terms of content, structure, shape, and visual features.
2. Overall image quality and clarity.

Below is the metadata for each model to just help a little with the decision.
If it is professional, it may be an unconfirmed hint that the real model is good.
Note: they may be incorrect or good-looking but the actual image (3D model) is bad, so don't primarily depend on it.

{models_metadata}

Summary: Select the ONE image that best represents the topic "{self.topic_name}".


**Task2**
The topic the student is learning about: "{self.topic_name}"
Analyze the exact image (3D model) you chose from task 1, and write a clear, educational description.

Your description should:
1. Provide information about the topic with a few refers to parts from the model.
2. Highlight important details visible in the 3D model.
3. Connect it directly to the topic "{self.topic_name}".
4. Use simple, student-friendly language.
5. Be 3-7 lines long.

Focus on helping students understand the topic better through this visual representation.
Markdown is available.


You should return your response in a JSON structure like this example:
{{
    "best_model_index": 0,  # 0-indexed
    "description": "Your description here"
}}
"""

        # --- 4. Adding each image's data to the contents ---
        contents = [prompt]
        for image_data in images:
            contents.append(
                types.Part.from_bytes(
                    data=image_data["bytes"], mime_type=image_data["mime_type"]
                )
            )

        # --- 5. Generating the response ---
        for model in [
            "gemini-3.1-flash-preview",
            "gemini-3.1-flash-lite-preview",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]:
            print(model)
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )
                break
            except:
                continue

        response_json = json.loads(response.text)

        model_index = int(response_json["best_model_index"])

        # --- 5. Returning the model UID and description ---
        return (models[model_index]["uid"], response_json["description"])

    def download_model(self, model_uid: str, type: str = "glb") -> bytes:
        sketchfab_download_endpoint = (
            f"https://api.sketchfab.com/v3/models/{model_uid}/download"
        )

        # Sending the request to get the downloads options
        response = requests.get(
            sketchfab_download_endpoint, headers=self.authorization_header
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise SketchfabDownloadError("Couldn't get model from Sketchfab.") from e

        # Downloading the model's type
        model_url = response.json().get(type, {}).get("url")

        if model_url:
            try:
                response = requests.get(model_url)
                response.raise_for_status()
                return response.content

            except requests.RequestException as e:
                raise SketchfabDownloadError("Couldn't download model from URL.") from e

        else:
            raise SketchfabDownloadError(f'No file found of type "{type}".')

    def host_model_on_github(self, model_bytes: bytes) -> str:
        topic_name = self.topic_name.replace(" ", "")

        def generate_folder_id():
            characters = string.ascii_letters + string.digits
            return "".join(random.choice(characters) for _ in range(4))

        dest_path = f"{topic_name}_{generate_folder_id()}/{topic_name}.glb"

        # Encode to base64 (GitHub requirement)
        content_b64 = base64.b64encode(model_bytes).decode("utf-8")

        # API endpoint
        url_endpoint = f"https://api.github.com/repos/{self.github_username}/{self.repo}/contents/{dest_path}"

        # Request headers
        headers = {
            "Authorization": f"token {self.github_access_token}",
            "Accept": "application/vnd.github+json",
        }

        # Request body
        data = {"message": f"Add {topic_name}.glb via API", "content": content_b64}

        # Upload file
        response = requests.put(url_endpoint, headers=headers, json=data)

        response.raise_for_status()
        hosted_model_url = f"https://raw.githubusercontent.com/{self.github_username}/{self.repo}/main/{dest_path}"
        return hosted_model_url

    def generate_ar_experience(
        self, topic_name: str = None, use_model_viewer: bool = False
    ):
        # Setting the topic name (if not provided before)
        if topic_name:
            self.topic_name = topic_name

        # --- 1. Searching for 3D models from Sketchfab, a huge 3D Library ---
        models = self.search_models()
        if not models:
            raise SketchfabError("Failed to search models on Sketchfab.")

        # --- 2. Detrmining the best describing image by Gemini + generating an AI description for it ---
        model_uid, description = self.best_model_and_ai_description(models)
        sketchfab_embed_html = self.sketchfab_embed_html(model_uid)

        # Yield first result immediately
        yield {
            "step": "embed_and_description",
            "model_sketchfab_uid": model_uid,
            "sketchfab_embed_html": sketchfab_embed_html,
            "ai_description": description,
        }

        # --- 3. Hosting the model on Github to view in AR, if requested ---
        if use_model_viewer:
            model_bytes = self.download_model(model_uid)
            hosted_model_url = self.host_model_on_github(model_bytes)
            model_viewer_html = self.model_viewer_html(hosted_model_url)

            yield {
                "step": "ar_viewer",
                "model_viewer_html": model_viewer_html,
            }

    @staticmethod
    def sketchfab_embed_html(model_uid: str):
        embed_url = f"https://sketchfab.com/models/{model_uid}/embed"
        return f"""
<div class="sketchfab-container">
    <iframe
        title="Sketchfab Model"
        src="{embed_url}"
        frameborder="0"
        allowfullscreen
        mozallowfullscreen="true"
        webkitallowfullscreen="true">
    </iframe>
</div>

<style>
    .sketchfab-container {{
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        border: 2px solid #EDEADE;
        border-radius: 12px;
    }}

    .sketchfab-container iframe {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border: 0;
    }}
</style>
"""

    @staticmethod
    def model_viewer_html(hosted_model_url):
        return f"""
        <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
        <style>
            button {{
                padding: 10px 14px;
                font-size: 14px;
                background: #0a84ff;
                color: white;
                border: none;
                width: 100%;
                border-radius: 7px;
            }}
        </style>

        <model-viewer
            src="{hosted_model_url}"
            ios-src="https://modelviewer.dev/shared-assets/models/Astronaut.usdz"
            alt="3D Model"
            ar
            reveal="interaction"
        >
            <button slot="ar-button">👀 View in AR</button>
        </model-viewer>
        """
