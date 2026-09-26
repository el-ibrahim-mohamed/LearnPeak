from datetime import datetime
from firebase_admin.db import Reference
from typing import Dict, List, Optional
import uuid


class ChatService:
    """Simplified chat persistence service using Firebase RTDB"""

    def __init__(self, root_ref: Reference, user_uid: str):
        self.root_ref = root_ref
        self.user_uid = user_uid

    def create_chat(self, title: str = "New Chat") -> str:
        """Create new chat and return chat_id"""
        chat_id = str(uuid.uuid4())
        chat_ref = self.root_ref.child(f"users/{self.user_uid}/history/chats/{chat_id}")
        chat_ref.set(
            {"id": chat_id, "title": title, "created_at": datetime.now().isoformat()}
        )
        return chat_id

    def save_message(
        self,
        chat_id: str,
        user_prompt: str,
        user_timestamp: str,
        ai_response: str,
        user_files: Optional[List[Dict]] = None,
    ):
        """Save user prompt (with optional files metadata) and AI response to chat"""

        user_msg = {
            "role": "user",
            "content": user_prompt,
            "timestamp": user_timestamp,
        }

        # Include files metadata if present
        if user_files:
            user_msg["files"] = user_files

        assistant_msg = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat(),
        }

        self.root_ref.child(
            f"users/{self.user_uid}/history/chats/{chat_id}/messages/"
        ).update({str(uuid.uuid4()): user_msg, str(uuid.uuid4()): assistant_msg})

    def get_chats(self, user_uid: str) -> List[Dict]:
        """Get all chats for user, sorted by recency"""
        if user_uid != self.user_uid:
            return []

        try:
            chats_ref = self.root_ref.child(f"users/{self.user_uid}/history/chats")
            chats_data = chats_ref.get()

            if not chats_data:
                return []

            chats = list(chats_data.values())
            result = sorted(chats, key=lambda x: x.get("created_at", ""), reverse=True)
            return result
        except:
            return []

    def get_chat_messages(self, chat_id: str) -> List[Dict]:
        """Get all messages for a chat"""
        try:
            msgs_ref = self.root_ref.child(
                f"users/{self.user_uid}/history/chats/{chat_id}/messages"
            )
            msgs_data: dict = msgs_ref.get()

            if not msgs_data:
                return []

            msgs = list(msgs_data.values())
            return sorted(msgs, key=lambda x: x.get("timestamp", ""))
        except:
            return []

    def update_title(self, chat_id: str, title: str):
        """Update chat title"""
        self.root_ref.child(f"users/{self.user_uid}/history/chats/{chat_id}").update(
            {"title": title}
        )

    def save_message_and_title(
        self,
        chat_id: str,
        user_prompt: str,
        user_timestamp: str,
        ai_response: str,
        title: str,
        user_files: Optional[List[Dict]] = None,
    ): 
        """Save user message and title on the first prompt in one request to save time"""

        user_msg = {
            "role": "user",
            "content": user_prompt,
            "timestamp": user_timestamp,
        }

        # Include files metadata if present
        if user_files:
            user_msg["files"] = user_files

        assistant_msg = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat(),
        }

        self.root_ref.child(f"users/{self.user_uid}/history/chats/{chat_id}/").update({
            f"messages/{str(uuid.uuid4())}": user_msg,
            f"messages/{str(uuid.uuid4())}": assistant_msg,
            "title": title,
        })
    
    def delete_chat(self, chat_id: str):
        """Delete a chat"""
        self.root_ref.child(f"users/{self.user_uid}/history/chats/{chat_id}").delete()
