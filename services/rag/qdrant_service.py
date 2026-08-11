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
