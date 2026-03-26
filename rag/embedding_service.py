from sentence_transformers import SentenceTransformer
from typing import List


class EmbeddingService:
    """
    Handles text-to-vector embedding generation.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self):
        self.model = SentenceTransformer(self.MODEL_NAME)

    def embed_text(self, text: str) -> List[float]:
        embedding = self.model.encode(
            text,
            normalize_embeddings=True
        )
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
        )
        return embeddings.tolist()
    @property
    def vector_size(self) -> int:
        return self.model.get_sentence_embedding_dimension()