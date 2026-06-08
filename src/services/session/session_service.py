from typing import Any, Dict, List
import uuid
from repositories.student_persona_repo import StudentPersonaRepo
from dtos.redis_session_dto import RedisSessionDTO
from dtos.session_archive_metadata_dto import SessionArchiveMetadataDTO
from dtos.vdb_payload_dto import VDBChunkPayload
from helpers.logger import get_logger
from integrations.redis_provider import RedisProvider
from integrations.llm import LLMInterface
from schemas.session_schema import SessionEndResponse, SessionRequest, SessionStartResponse
from services.embedding.embedding_service import ChunkEmbeddingService
from .session_exceptions import SessionNotFoundError, SessionProcessingError, SessionValidationError
from services.vdb_service.vectordb_service import VDBService


logger = get_logger(__name__)


class SessionService:
    COLLECTION_NAME = "sessions"

    def __init__(
        self,
        redis_provider: RedisProvider,
        embedding_client: LLMInterface,
        vdb_service: VDBService,
        student_persona_repo: StudentPersonaRepo,
    ):
        self.redis_provider = redis_provider
        self.embedding_service = ChunkEmbeddingService(embedding_client=embedding_client)
        self.vdb_service = vdb_service
        self.student_persona_repo = student_persona_repo


    async def start_session(self, request: SessionRequest) -> SessionStartResponse:
        user_id = request.user_id
        session_id = request.session_id
        
        
        persona_doc = await self.student_persona_repo.get_persona_by_student_id(user_id)
        persona_str = persona_doc.persona if persona_doc else None

        collection = RedisSessionDTO(user_id=user_id, persona=persona_str)
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

        summary_text = collection.summary
        if not summary_text:
            logger.info("Running summary not found in Redis, falling back to build_session_text.")
            summary_text = self._build_session_text(messages)

        archive_metadata = SessionArchiveMetadataDTO(
            chunk_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"session:{user_id}:{session_id}")),
            user_id=user_id,
            session_id=session_id,
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
            raise SessionProcessingError(
                message="Failed to archive session into Qdrant",
                details={
                    "user_id": user_id,
                    "session_id": session_id,
                    "error": str(exc),
                },
            ) from exc

        if collection.persona:
            try:
                await self.student_persona_repo.upsert_persona(user_id, collection.persona)
                logger.info("Persona upserted to MongoDB for student_id: %s", user_id)
            except Exception as exc:
                logger.warning("Failed to upsert persona to MongoDB for student_id=%s: %s", user_id, exc)

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
