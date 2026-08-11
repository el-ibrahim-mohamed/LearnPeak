from fastembed import TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType
from typing import List, Literal


class EmbeddingService:
    """
    Handles text-to-vector embedding generation using FastEmbed.
    """

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        batch_size: int = 64,
    ):
        self.model_name = model_name
        self.batch_size = batch_size

        # Check if the model is already registered in FastEmbed
        supported_models = TextEmbedding.list_supported_models()
        model_exists = any(m["model"] == self.model_name for m in supported_models)

        # Register the custom model metadata if using e5-small
        if self.model_name == "intfloat/multilingual-e5-small" and not model_exists:
            TextEmbedding.add_custom_model(
                model=self.model_name,
                pooling=PoolingType.MEAN,
                normalization=True,
                dim=384,
                sources=ModelSource(hf=self.model_name),
                model_file="onnx/model.onnx",
            )

        # Initialize the FastEmbed text model engine
        self.model = TextEmbedding(model_name=self.model_name)

    def embed(
        self, texts: List[str], task: Literal["passage", "query"] = "passage"
    ) -> List[List[float]]:
        # Prepend the required E5 semantic prefix constraint
        texts = [f"{task}: {text}" for text in texts]

        # FastEmbed generates embeddings as an iterator of numpy arrays
        embeddings_iter = self.model.embed(texts, batch_size=self.batch_size)

        # Convert the generated embeddings into a clean list of lists
        return [embedding.tolist() for embedding in embeddings_iter]

    @property
    def vector_size(self) -> int:
        if self.model_name == "intfloat/multilingual-e5-small":
            return 384
