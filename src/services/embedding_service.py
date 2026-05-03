from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import Depends

from helpers import get_logger
from integrations.llm import LLMInterface
from core.request_dependencies import get_embedding_client
from models.vdb_payload_model import VDBChunkPayload

logger = get_logger(__name__)

class ChunkEmbeddingService:
    def __init__(self, embedding_client: LLMInterface):
        self.embedding_client = embedding_client

    async def embed_chunks(
        self,
        payloads: List[VDBChunkPayload],
        id_factory: Optional[Callable[[int], str]] = None,
        document_type: Optional[str] = None,
    ) -> Tuple[List[str], List[List[float]], List[str], List[Dict[str, Any]]]:
        texts: List[str] = []
        vectors: List[List[float]] = []
        ids: List[str] = []
        metas: List[dict] = []

        if id_factory is None:
            def id_factory(_: int) -> str:
                return str(uuid4())

        for index, payload in enumerate(payloads):
            text = str(payload.text).strip()
            if not text:
                logger.error("Chunk text is empty", extra={"chunk_index": index})
                raise ValueError("Chunk text is empty")

            try:
                if document_type is None:
                    vector = await self.embedding_client.embed_text(text)
                else:
                    try:
                        vector = await self.embedding_client.embed_text(
                            text,
                            document_type=document_type,
                        )
                    except TypeError:
                        vector = await self.embedding_client.embed_text(text)
            except Exception as exc:
                logger.error("Embedding failed", exc_info=True, extra={"chunk_index": index})
                raise RuntimeError("Embedding failed") from exc

            texts.append(text)
            vectors.append(vector)
            ids.append(id_factory(index))
            metas.append(payload.metadata)

        return texts, vectors, ids, metas


def get_chunk_embedding_service(
    embedding_client: LLMInterface = Depends(get_embedding_client),
) -> ChunkEmbeddingService:
    return ChunkEmbeddingService(embedding_client=embedding_client)
