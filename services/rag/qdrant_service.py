import json
from datetime import datetime
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from typing import Optional


class QdrantService:
    """
    Infrastructure layer for managing Qdrant collection lifecycle.
    """

    DEFAULT_COLLECTION_NAME = "learnpeak_knowledge"

    def __init__(
        self,
        url: str,
        api_key: str,
        timeout: int = 60,
        vector_size: int = 384,
        collection_name: Optional[str] = None,
    ):
        self.collection_name = collection_name or self.DEFAULT_COLLECTION_NAME
        self.vector_size = vector_size

        self.client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=timeout,
        )

    # -------------------------
    # Collection Management
    # -------------------------

    def collection_exists(self) -> bool:
        """Check if the collection already exists."""
        collections = self.client.get_collections().collections
        return any(c.name == self.collection_name for c in collections)

    def create_collection(self) -> None:
        """Create a fresh collection."""
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE,
            ),
        )

    def recreate_collection(self) -> None:
        """Delete and recreate the collection (useful for development)."""
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE,
            ),
        )

    def ensure_collection_exists(self) -> None:
        """Create collection only if it does not exist."""
        if not self.collection_exists():
            self.create_collection()

    def delete_collection(self) -> None:
        """Delete the collection."""
        if self.collection_exists():
            self.client.delete_collection(self.collection_name)

    def get_collection_info(self):
        """Return collection configuration and stats."""
        if not self.collection_exists():
            raise ValueError(f"Collection '{self.collection_name}' does not exist.")
        return self.client.get_collection(self.collection_name)

    def backup_payloads(self) -> None:
        """
        Collects every single payload across the entire Qdrant collection 
        and dumps them into a flat JSON list under db_backups/Qdrant/.
        """

        backup_data = []
        next_offset = None

        # 1. Fetch 100% of the points dynamically via cursor pagination
        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000, 
                with_payload=True,
                with_vectors=False,
                offset=next_offset
            )
            
            # 2. Extract and append only the raw payload data
            for point in points:
                if point.payload is not None:
                    backup_data.append(point.payload)
            
            if next_offset is None:
                break

        # 3. Ensure the backup folder structure exists
        backup_dir = "admin/db_backups/qdrant"
        os.makedirs(backup_dir, exist_ok=True)

        # 4. Create the dynamic timestamped filename and full path
        timestamp = datetime.now().isoformat(timespec="seconds").replace(":", "-")
        file_path = f"{backup_dir}/{timestamp}.json"

        # 5. Save the data cleanly into a flat list
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)


    def create_payload_index(
        self, collection_name: str, field_name: str, field_schema: None = None
    ):
        self.client.create_payload_index(
            collection_name,
            field_name,
            field_schema,
        )

    # -------------------------
    # Client Access
    # -------------------------

    def get_client(self) -> QdrantClient:
        """Expose the internal Qdrant client (read-only usage in services)."""
        return self.client
