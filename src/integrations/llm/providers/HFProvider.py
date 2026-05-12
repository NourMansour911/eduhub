from typing import List, Optional
import numpy as np
import asyncio
from sentence_transformers import SentenceTransformer

from ..llm_interface import LLMInterface
from helpers import get_logger

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
        self.embedding_model_id = model_id
        logger.info(f"Loading embedding model: {model_id}")

        self.client = SentenceTransformer(model_id)

        if not embedding_size:
            embedding_size = self.client.get_sentence_embedding_dimension()

        self.embedding_size = embedding_size
        logger.info(f"Embedding model initialized. Size: {embedding_size}")

    def generate_text(self, *args, **kwargs):
        raise NotImplementedError("HuggingFaceProvider doesn't support text generation")

    async def embed_text(
        self,
        text: List[str],
        document_type: Optional[str] = None,
    ) -> List[List[float]]:
        embeddings = await asyncio.to_thread(
            self.client.encode,
            text,
            batch_size=32,
            convert_to_tensor=False,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )

        return self._to_list_format(embeddings)

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