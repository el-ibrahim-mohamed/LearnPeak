from datetime import datetime
from firebase_admin.db import Reference
from typing import Dict, List
import uuid


class ChatService:
    """Simplified chat persistence service using Firebase RTDB"""

    def __init__(self, root_ref):
        self.root_ref: Reference = root_ref

    def create_chat(self, username: str, title: str = "New Chat") -> str:
        """Create new chat and return chat_id"""
        chat_id = str(uuid.uuid4())
        chat_ref = self.root_ref.child(f"users/{username}/history/chats/{chat_id}")
        chat_ref.set(
            {"id": chat_id, "title": title, "created_at": datetime.now().isoformat()}
        )
        return chat_id

    def save_message(
        self,
        username: str,
        chat_id: str,
        role: str,
        content: str,
        similar_questions: list = None,
    ):
        """Save message to chat"""
        msg_id = str(datetime.now().timestamp()).replace(".", "")

        data = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

        if similar_questions:
            data["similar_questions"] = similar_questions

        self.root_ref.child(
            f"users/{username}/history/chats/{chat_id}/messages/{msg_id}"
        ).set(data)

    def get_chats(self, username: str) -> List[Dict]:
        """Get all chats for user, sorted by recency"""
        try:
            chats_ref = self.root_ref.child(f"users/{username}/history/chats")
            chats_data = chats_ref.get()

            if not chats_data:
                return []

            chats = list(chats_data.values())
            result = sorted(chats, key=lambda x: x.get("created_at", ""), reverse=True)
            return result
        except:
            return []

    def get_chat_messages(self, username: str, chat_id: str) -> List[Dict]:
        """Get all messages for a chat"""
        try:
            msgs_ref = self.root_ref.child(
                f"users/{username}/history/chats/{chat_id}/messages"
            )
            msgs_data = msgs_ref.get()

            if not msgs_data:
                return []

            msgs = list(msgs_data.values())
            return sorted(msgs, key=lambda x: x.get("timestamp", ""))
        except:
            return []

    def prepare_conversation_history(self, username: str, chat_id: str) -> List[Dict]:
        """Return messages formatted for LLM input"""
        msgs = self.get_chat_messages(username, chat_id)
        if not msgs:
            return []

        msgs = [{"role": m["role"], "content": m["content"]} for m in msgs]
        if msgs and msgs[-1]["role"] == "user":
            msgs = msgs[:-1]

    def update_title(self, username: str, chat_id: str, title: str):
        """Update chat title"""
        self.root_ref.child(f"users/{username}/history/chats/{chat_id}").update(
            {"title": title}
        )

    def delete_chat(self, username: str, chat_id: str):
        """Delete a chat"""
        self.root_ref.child(f"users/{username}/history/chats/{chat_id}").delete()
