from sentence_transformers import SentenceTransformer
from typing import List, Literal


class EmbeddingService:
    """
    Handles text-to-vector embedding generation.
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
    ):
        self.model = SentenceTransformer(model_name)

    def embed(
        self, texts: List[str], type: Literal["passage", "query"] = "passage"
    ) -> List[List[float]]:
        texts = [f"{type}: {text}" for text in texts]
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    @property
    def vector_size(self) -> int:
        return 384
