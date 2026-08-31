import requests
import mimetypes
from firebase_admin.db import Reference
from google.genai import Client, types
import string
import random
import base64
import uuid
import time
from .errors import *
from config import GEMINI_LITE_FIRST


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

    def search_models(self, topic_name: str, quantity: int = 20) -> list:
        sketchfab_search_endpoint = "https://api.sketchfab.com/v3/search"
        params = {
            "q": topic_name,
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

        return response.json().get("results", [])

    def generate_ai_description(self, topic_name: str, model_data: dict) -> str:
        """Generates an educational description for a user-selected model."""
        images = model_data.get("thumbnails", {}).get("images", [])
        thumbnail_url = (
            images[1]["url"]
            if len(images) > 1
            else (images[0]["url"] if images else "")
        )
        title = model_data.get("name", "")
        description = model_data.get("description", "")

        contents = []
        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url)
                response.raise_for_status()
                image_bytes = response.content
                mime_type, _ = mimetypes.guess_type(thumbnail_url)
                if not mime_type:
                    mime_type = "image/jpeg"
                contents.append(
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                )
            except requests.RequestException:
                pass

        prompt = f"""You are an AI assistant in an educational platform.
The topic the student is learning about: "{topic_name}".
Model Title: {title}
Model Description: {description}

Analyze the provided image (3D model thumbnail) and write a clear, educational description.

Your description should:
1. Provide information about the topic with a few references to parts visible in the model.
2. Highlight important details visible in the 3D model.
3. Connect it directly to the topic "{topic_name}".
4. Use simple, student-friendly language.
5. Be 3-7 lines long.

Markdown formatting is supported.
"""
        contents.insert(0, prompt)

        for model in GEMINI_LITE_FIRST:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                    ),
                )
                return response.text
            except Exception:
                continue

        raise Exception("Failed to generate AI description with Gemini.")

    def download_model(self, model_uid: str, type: str = "glb") -> bytes:
        sketchfab_download_endpoint = (
            f"https://api.sketchfab.com/v3/models/{model_uid}/download"
        )

        response = requests.get(
            sketchfab_download_endpoint, headers=self.authorization_header
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise SketchfabDownloadError("Couldn't get model from Sketchfab.") from e

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

    def host_model_on_github(self, topic_name: str, model_bytes: bytes) -> str:
        topic_name = topic_name.replace(" ", "")

        def generate_folder_id():
            characters = string.ascii_letters + string.digits
            return "".join(random.choice(characters) for _ in range(4))

        dest_path = f"{topic_name}_{generate_folder_id()}/{topic_name}.glb"

        content_b64 = base64.b64encode(model_bytes).decode("utf-8")

        url_endpoint = f"https://api.github.com/repos/{self.github_username}/{self.repo}/contents/{dest_path}"

        headers = {
            "Authorization": f"token {self.github_access_token}",
            "Accept": "application/vnd.github+json",
        }

        data = {"message": f"Add {topic_name}.glb via API", "content": content_b64}

        response = requests.put(url_endpoint, headers=headers, json=data)
        response.raise_for_status()
        hosted_model_url = f"https://raw.githubusercontent.com/{self.github_username}/{self.repo}/main/{dest_path}"
        return hosted_model_url

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


class ARHistory:

    def __init__(self, root_ref: Reference):
        self.root_ref = root_ref

    def save_ar_experience(
        self,
        user_uid: str,
        topic: str,
        sketchfab_embed_html: str,
        sketchfab_uid: str = "",
        thumbnail_url: str = "",
        ai_description: str = "",
        model_viewer_html: str = None,
    ) -> str:
        id = str(uuid.uuid4())
        ar_ref = self.root_ref.child(f"users/{user_uid}/history/ar")

        ar_saving_data = {
            "topic": topic,
            "id": id,
            "created_at": time.time(),
            "sketchfab_embed_html": sketchfab_embed_html,
            "sketchfab_uid": sketchfab_uid,
            "thumbnail_url": thumbnail_url,
            "ai_description": ai_description,
        }

        if model_viewer_html:
            ar_saving_data["model_viewer_html"] = model_viewer_html

        ar_ref.child(id).set(ar_saving_data)

        return id

    def update_ar_experience(self, user_uid: str, model_id: str, updates: dict):
        """Dynamically update an existing saved record in Firebase."""
        if not user_uid or not model_id or not updates:
            return
        ar_ref = self.root_ref.child(f"users/{user_uid}/history/ar/{model_id}")
        ar_ref.update(updates)

    def get_saved_ar_data(self, user_uid: str) -> list[dict]:
        ar_ref = self.root_ref.child(f"users/{user_uid}/history/ar")
        ar_data_dict: dict = ar_ref.get()

        ar_models = []
        if ar_data_dict:
            for ar_id, ar_model in ar_data_dict.items():
                ar_models.append({"id": ar_id, **ar_model})
            ar_models.sort(key=lambda x: x.get("created_at", 0), reverse=True)

        return ar_models

    def delete_ar_experience(self, user_uid: str, model_id: str):
        self.root_ref.child(f"users/{user_uid}/history/ar/{model_id}").delete()