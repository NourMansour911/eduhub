from ..llm_interface import LLMInterface
from sentence_transformers import SentenceTransformer
from helpers import get_logger
from ..llm_exceptions import (
    LLMInitializationException,
    LLMEmbeddingException,
    LLMModelNotSetException,
)

logger = get_logger(__name__)


class HuggingFaceProvider(LLMInterface):
    def __init__(
        self,
    ):
        self.embedding_model_id = None
        self.embedding_size = None
        self.client = None

    def set_generation_model(self, model_id: str):
        raise NotImplementedError("HuggingFaceProvider doesn't support text generation")

    def set_embedding_model(self, model_id: str, embedding_size: int = None):
        try:
            self.embedding_model_id = model_id
            self.client = SentenceTransformer(model_id)

            if not embedding_size:
                sample_embedding = self.client.encode("test")
                embedding_size = len(sample_embedding)

            self.embedding_size = embedding_size

        except Exception as e:
            raise LLMInitializationException(
                provider="HuggingFace",
                init_error=str(e),
            )

    def generate_text(self, *args, **kwargs):
        raise NotImplementedError

    async def embed_text(self, text: str, document_type: str = None):
        if not self.client:
            raise LLMModelNotSetException(
                operation="embedding",
                model_type="embedding",
                provider="HuggingFace",
            )

        try:
            embedding = self.client.encode(text)
            return embedding.tolist() if hasattr(embedding, "tolist") else embedding

        except Exception as e:
            raise LLMEmbeddingException(
                model_id=self.embedding_model_id,
                text_sample=text[:50],
                embedding_error=str(e),
            )