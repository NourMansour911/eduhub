from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import Depends
from langchain_openai import ChatOpenAI

from core import Settings, get_settings
from core.request_dependencies import (
    get_langchain_client,
    get_redis_provider,
)
from dtos import RedisSessionDTO, SessionArchiveMetadataDTO, VDBChunkPayload
from helpers import get_logger
from integrations import RedisProvider
from integrations.llm import LCOpenAI
from schemas.session_schema import SessionEndResponse, SessionRequest, SessionStartResponse
from services.embedding import ChunkEmbeddingService, get_chunk_embedding_service
from .session_exceptions import SessionNotFoundError, SessionProcessingError, SessionValidationError
from services.vdb_service import VDBService, get_vdb_service
from .session_chain import build_session_summary_chain

logger = get_logger(__name__)


class SessionService:
    COLLECTION_NAME = "sessions"

    def __init__(
        self,
        redis_provider: RedisProvider,
        summary_llm: ChatOpenAI,
        embedding_service: ChunkEmbeddingService,
        vdb_service: VDBService,
    ):
        self.redis_provider = redis_provider
        self.embedding_service = embedding_service
        self.vdb_service = vdb_service
        self.summary_chain = build_session_summary_chain(summary_llm)

    async def start_session(self, request: SessionRequest) -> SessionStartResponse:
        user_id = request.user_id
        session_id = request.session_id
        collection = RedisSessionDTO(user_id=user_id)
        await self.redis_provider.save_collection(collection, session_id=session_id)

        return SessionStartResponse(
            cache_key=self.redis_provider.build_collection_key(user_id=user_id, session_id=session_id),
        )

    async def end_session(self, request: SessionRequest) -> SessionEndResponse:
        user_id = request.user_id
        session_id = request.session_id
        collection = await self.redis_provider.get_collection(user_id=user_id, session_id=session_id)
        if collection is None:
            raise SessionNotFoundError(
                message="Session not found",
                details={"user_id": user_id, "session_id": session_id},
            )

        messages = collection.messages or []
        message_count = len(messages)
        if message_count == 0:
            raise SessionValidationError(
                message="Session has no messages to archive",
                details={"user_id": user_id, "session_id": session_id},
            )

        session_text = self._build_session_text(messages)
        summary_text = session_text

        if message_count > 1:
            try:
                summary_text = await self.summary_chain.ainvoke(
                    {"messages": session_text},
                    config={
                        "run_name": "session_summary_run",
                        "metadata": {
                            "user_id": user_id,
                            "session_id": session_id,
                            "messages_count": message_count,
                        },
                    },
                )
            except Exception as exc:
                logger.error(
                    "Failed to generate session summary",
                    exc_info=True,
                    extra={"user_id": user_id, "session_id": session_id},
                )
                raise SessionProcessingError(
                    message="Failed to generate session summary",
                    details={
                        "user_id": user_id,
                        "session_id": session_id,
                        "error": str(exc),
                    },
                ) from exc

        archive_metadata = SessionArchiveMetadataDTO(
            chunk_id=f"session:{user_id}:{session_id}",
            user_id=user_id,
            session_id=session_id,
            messages_count=message_count,
            summary_generated=message_count > 1,
            archived_at=datetime.now(timezone.utc),
        )

        payload = VDBChunkPayload(
            text=summary_text,
            metadata=archive_metadata.model_dump(mode="json"),
        )

        try:
            texts, vectors, ids, metas = await self.embedding_service.embed_chunks(
                [payload],
                document_type="session",
            )
            await self.vdb_service.store_batch(
                collection_name=self.COLLECTION_NAME,
                batch_size=1,
                texts=texts,
                vectors=vectors,
                record_ids=ids,
                metadatas=metas,
                use_bm25=True,
                fields_for_indexing=[
                    {"name": "user_id", "type": str},
                    {"name": "session_id", "type": str},
                    {"name": "archived_at", "type": str},
                ],
            )
        except Exception as exc:
            logger.error(
                "Failed to archive session into Qdrant",
                exc_info=True,
                extra={"user_id": user_id, "session_id": session_id},
            )
            raise SessionProcessingError(
                message="Failed to archive session into Qdrant",
                details={
                    "user_id": user_id,
                    "session_id": session_id,
                    "error": str(exc),
                },
            ) from exc

        await self.redis_provider.clear_session_collection(user_id=user_id, session_id=session_id)

        return SessionEndResponse(
            summary=summary_text,
            vdb_record_id=ids[0] if ids else None,
        )

    def _build_session_text(self, messages: List[Dict[str, Any]]) -> str:
        rendered_messages: List[str] = []
        for index, message in enumerate(messages, start=1):
            role = str(message.get("role", "message")).strip() or "message"
            content = message.get("content")
            if content is None:
                content = message.get("text")
            if content is None:
                content = str(message)

            rendered_messages.append(f"{index}. {role}: {content}")

        return "\n".join(rendered_messages)


def get_session_service(
    redis_provider: RedisProvider = Depends(get_redis_provider),
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
    embedding_service: ChunkEmbeddingService = Depends(get_chunk_embedding_service),
    vdb_service: VDBService = Depends(get_vdb_service),
    settings: Settings = Depends(get_settings),
) -> SessionService:
    summary_llm = lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID,
        temperature=0.1,
        top_p=0.85,
    )

    return SessionService(
        redis_provider=redis_provider,
        summary_llm=summary_llm,
        embedding_service=embedding_service,
        vdb_service=vdb_service,
    )