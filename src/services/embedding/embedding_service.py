from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends

from core.request_dependencies import get_embedding_client
from helpers import get_logger
from integrations.llm import LLMInterface
from models.vdb_payload_model import VDBChunkPayload

from .embedding_exceptions import EmbeddingGenerationError

logger = get_logger(__name__)


class ChunkEmbeddingService:
    def __init__(self, embedding_client: LLMInterface):
        self.embedding_client = embedding_client

    async def embed_chunks(
        self,
        payloads: List[VDBChunkPayload],
        document_type: Optional[str] = None,
    ) -> Tuple[List[str], List[List[float]], List[str], List[Dict[str, Any]]]:
        texts: List[str] = [str(payload.text) for payload in payloads]
        ids: List[str] = [payload.metadata["chunk_id"] for payload in payloads]
        metas: List[Dict[str, Any]] = [payload.metadata for payload in payloads]

        try:
            
            vectors = await self.embedding_client.embed_text(texts, document_type=document_type)
        except Exception as exc:
            logger.error("Embedding failed", exc_info=True)
            raise EmbeddingGenerationError(details={"error": str(exc)}) from exc

        return texts, vectors, ids, metas


def get_chunk_embedding_service(
    embedding_client: LLMInterface = Depends(get_embedding_client),
) -> ChunkEmbeddingService:
    return ChunkEmbeddingService(embedding_client=embedding_client)