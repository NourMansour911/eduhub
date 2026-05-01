from typing import List, Union
import numpy as np
import asyncio
from sentence_transformers import SentenceTransformer

from ..llm_interface import LLMInterface
from helpers import get_logger
from ..llm_exceptions import (
    LLMInitializationException,
    LLMEmbeddingException,
    LLMModelNotSetException,
)

logger = get_logger(__name__)


class HuggingFaceProvider(LLMInterface):
    def __init__(self):
        self.embedding_model_id = None
        self.embedding_size = None
        self.client = None
        self.normalize_embeddings = True

    def set_generation_model(self, model_id: str):
        raise NotImplementedError("HuggingFaceProvider doesn't support text generation")

    def set_embedding_model(self, model_id: str, embedding_size: int = None):
        try:
            self.embedding_model_id = model_id
            logger.info(f"Loading embedding model: {model_id}")

            self.client = SentenceTransformer(model_id)


            if not embedding_size:
                embedding_size = self.client.get_sentence_embedding_dimension()

            self.embedding_size = embedding_size

            logger.info(f"Embedding model initialized. Size: {embedding_size}")

        except Exception as e:
            logger.error(f"Failed to initialize model: {model_id}", exc_info=True)
            raise LLMInitializationException(
                provider="HuggingFace",
                init_error=str(e),
            )

    def generate_text(self, *args, **kwargs):
        raise NotImplementedError("HuggingFaceProvider doesn't support text generation")

    async def embed_text(
        self,
        text: Union[str, List[str]],
        document_type: str = None,
    ):
        if not self.client:
            raise LLMModelNotSetException(
                operation="embedding",
                model_type="embedding",
                provider="HuggingFace",
            )

        try:
            is_list_input = isinstance(text, list)
            texts = text if is_list_input else [text]

            if not texts:
                raise ValueError("Empty text input")


            embeddings = await asyncio.to_thread(
                self.client.encode,
                texts,
                batch_size=32,
                convert_to_tensor=False,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
            )

            embeddings_list = self._to_list_format(embeddings)

            return embeddings_list if is_list_input else embeddings_list[0]

        except Exception as e:
            logger.error(
                f"Embedding failed for model: {self.embedding_model_id}",
                exc_info=True,
            )
            raise LLMEmbeddingException(
                model_id=self.embedding_model_id,
                text_sample=str(text)[:50],
                embedding_error=str(e),
            )

    def _to_list_format(self, embeddings) -> List[List[float]]:
        if isinstance(embeddings, np.ndarray):
            if embeddings.ndim == 1:
                return [embeddings.tolist()]
            return embeddings.tolist()

        elif hasattr(embeddings, "tolist"):
            result = embeddings.tolist()
            if isinstance(result[0], (int, float)):
                return [result]
            return result

        elif isinstance(embeddings, list):
            if embeddings and isinstance(embeddings[0], (int, float)):
                return [embeddings]
            return embeddings

        return [list(embeddings)]