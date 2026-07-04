import asyncio
import json
import time
from typing import Any, List, Dict
from langchain_core.runnables import Runnable

from core import Settings
from helpers.logger import get_chatbot_logger
from integrations.redis_provider import RedisProvider
from integrations.llm import LCOpenAI
from models import EvaluationModel
from models.evaluation_model import RequestLayer, RetrievalLayer, GenerationLayer, PerformanceLayer
from repositories.evaluation_repo import EvaluationRepo
from repositories.student_persona_repo import StudentPersonaRepo
from schemas import ChatRequest, ChatResponse
from schemas.assistant_schema import DeletePersonaResponse
from dtos.redis_session_dto import RedisSessionDTO
from services.service_exceptions import NotFoundError, ProcessingError

from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools
from services.chatbot.agents.rag.retrieving.vdb.search_service import SearchService
from services.lectures.lecture_service import LectureService
from services.summarize.summarize_service import SummarizeService

from .agents.rag.builder import build_rag_subgraph
from .builder import build_chatbot_graph
from services.session.session_exceptions import SessionNotFoundError
from .chatbot_exceptions import ChatbotExternalError, ChatbotProcessingError, ChatbotValidationError
from .chains.summary_chain import build_summary_chain
from .chains.persona_chain import build_persona_chain

from services.chatbot.agents.rag.retrieving.sql.sql_server_calling import SqlServerCalling
from services.chatbot.utils import format_student_courses, format_chat_history_for_graph, deduplicate_tool_outputs, clip_message_content

logger = get_chatbot_logger(__name__)


class ChatbotService:
    def __init__(
        self,
        lc_openai_client: LCOpenAI,
        settings: Settings,
        vdb_client: Any,
        embedding_client: Any,
        lecture_service: LectureService,
        summarize_service: SummarizeService,
        redis_provider: RedisProvider,
        evaluation_repo: EvaluationRepo,
        student_persona_repo: StudentPersonaRepo,
    ) -> None:
        sql_server_calling = SqlServerCalling(base_url=settings.DB_BASE_URL)
        self.sql_tools = SQLTools(embedding_client=embedding_client, sql_server_calling=sql_server_calling)
        self.redis_provider = redis_provider
        self.evaluation_repo = evaluation_repo
        self.student_persona_repo = student_persona_repo


        search_service = SearchService(
            vdb_client=vdb_client,
            embedding_client=embedding_client,
            settings=settings,
            langchain_client=lc_openai_client,
        )
        vdb_tools = VDBTools(search_service=search_service)
        mongodb_tools = MongoDBTools(
            lecture_service=lecture_service,
            summarize_service=summarize_service,
        )

        llm_map = {
            "orchestrator": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.0
            ),
            "answering": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.7
            ),
            "summary": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.2
            ),
            "persona": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.1
            ),
        }

        self.rag_subgraph = build_rag_subgraph(
            lc_openai_client=lc_openai_client,
            settings=settings,
            vdb_tools=vdb_tools,
            mongodb_tools=mongodb_tools,
            sql_tools=self.sql_tools,
            redis_provider=redis_provider,
        )
        self.chatbot_graph: Runnable = build_chatbot_graph(
            llm_map=llm_map,
            rag_subgraph=self.rag_subgraph,
            redis_provider=self.redis_provider,
        )
        self.summary_chain = build_summary_chain(llm_map["summary"])
        self.persona_chain = build_persona_chain(llm_map["persona"])
        self.generation_model_id = settings.GENERATION_MODEL_ID

    async def _get_and_cache_student_courses(self, student_id: str, collection: RedisSessionDTO) -> str:
        if collection.student_courses:
            logger.info("Using cached student_courses from Redis: %s", collection.student_courses)
            return collection.student_courses

        logger.info("student_courses not found in Redis, retrieving from SQL server for student_id: %s", student_id)
        try:
            courses = await self.sql_tools.sql_server_calling.get_student_courses(student_id)
            courses_str = format_student_courses(courses)
        except Exception as exc:
            logger.warning("Failed to retrieve student courses from SQL. Error: %s. Falling back to placeholder.", exc)
            courses_str = "Information temporarily unavailable"
        
        collection.student_courses = courses_str
        logger.info("Cached formatted student_courses: %s", courses_str)
        return courses_str

    def _update_session_contexts(self, collection: RedisSessionDTO, run_step_outputs: List[Any]) -> None:
        if run_step_outputs:
            collection.contexts.append(run_step_outputs)
            logger.debug("Appended %d run step outputs to Redis session contexts.", len(run_step_outputs))

    async def chat(self, payload: ChatRequest, student_id: str, session_id: str) -> ChatResponse:
        user_query = (payload.message or "").strip()
        query_len = len(user_query)
        if query_len > 1000:
            raise ChatbotValidationError(
                message=f"Query is too long ({query_len} characters). Maximum allowed length is 1000 characters.",
                details={"query_len": query_len, "max_limit": 1000}
            )

        student_id = (student_id or "").strip()
        if not student_id:
            raise ChatbotValidationError(
                message="student_id is required",
                details={"student_id": student_id},
            )

        session_id = (session_id or "").strip()
        if not session_id:
            raise ChatbotValidationError(
                message="session_id is required",
                details={"session_id": session_id},
            )

        logger.info("Chatbot session run initiated. student_id: %s | session_id: %s", student_id, session_id)

        collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
        if collection is None:
            raise SessionNotFoundError(
                message="Active session not found. Please start a session before chatting.",
                details={"student_id": student_id, "session_id": session_id}
            )

        student_courses = await self._get_and_cache_student_courses(student_id, collection)

        last_messages = format_chat_history_for_graph(collection.messages or [], limit=6)
        logger.info("Formatted last messages of chat history: %s", last_messages)

        try:
            _t0 = time.perf_counter()
            graph_result = await self.chatbot_graph.ainvoke({
                "user_query": user_query,
                "student_id": student_id,
                "session_id": session_id,
                "student_courses": student_courses,
                "messages_history": last_messages,
                "user_persona": collection.persona,
                "session_summary": collection.summary,
            }, config={"run_name": "Chatbot Graph Run"})
            latency_ms = round((time.perf_counter() - _t0) * 1000, 2)
        except Exception as exc:
            logger.exception("Chatbot graph invocation failed")
            raise ChatbotProcessingError(
                message="Chatbot graph execution failed",
                details={"student_id": student_id, "session_id": session_id, "error": str(exc)},
            ) from exc

        ai_reply = graph_result.get("response") or "I'm sorry, I could not generate a response."
        logger.info("Chatbot graph result response: %s", ai_reply)

        
        response_obj = ChatResponse(ai_response=ai_reply)
        cleaned_reply = response_obj.ai_response

        collection.messages.append({"role": "user", "content": user_query})
        collection.messages.append({"role": "assistant", "content": cleaned_reply})

        run_step_outputs = graph_result.get("run_step_outputs") or []
        self._update_session_contexts(collection, run_step_outputs)

        await self.redis_provider.save_collection(collection, session_id=session_id)
        logger.info(
            "Redis session collection saved. Current Redis State:\n%s",
            json.dumps(collection.model_dump(), indent=2, ensure_ascii=False, default=str),
        )

        asyncio.create_task(self._push_evaluation(
            user_query=user_query,
            context=graph_result.get("retrieved_context") or "",
            answer=cleaned_reply,
            student_id=student_id,
            session_id=session_id,
            run_step_outputs=run_step_outputs,
            persona=collection.persona,
            summary=collection.summary,
            llm_usage=graph_result.get("llm_usage") or {},
            llm_metadata=graph_result.get("llm_metadata") or {},
            llm_usage_breakdown=graph_result.get("llm_usage_breakdown") or {},
            latency_ms=latency_ms,
        ))

        needs_persona_update = graph_result.get("needs_persona_update", False)
        needs_summary_update = graph_result.get("needs_summary_update", False)

        if not hasattr(collection, "unsummarized_count") or collection.unsummarized_count is None:
            collection.unsummarized_count = 0

        if needs_summary_update:
            collection.unsummarized_count += 2

        should_run_summary_now = False
        if needs_summary_update and collection.unsummarized_count >= 6:
            should_run_summary_now = True

        if needs_persona_update or should_run_summary_now:
            batch_history_str = ""
            for msg in collection.messages[-8:]:
                role = "User" if msg.get("role") == "user" else "AI"
                clipped_content = clip_message_content(msg.get("content", ""))
                batch_history_str += f"{role}: {clipped_content}\n"

            asyncio.create_task(self._update_persona_and_summary_background(
                student_id=student_id,
                session_id=session_id,
                user_query=user_query,
                batch_history_str=batch_history_str,
                current_persona=collection.persona,
                current_summary=collection.summary,
                run_persona=needs_persona_update,
                run_summary=should_run_summary_now
            ))

        return response_obj

    async def _update_persona_and_summary_background(
        self, student_id: str, session_id: str, user_query: str,
        batch_history_str: str, current_persona: str, current_summary: str,
        run_persona: bool, run_summary: bool
    ) -> None:
        try:
            logger.info("Starting background update for persona/summary (dynamic mode). run_persona=%s, run_summary=%s", run_persona, run_summary)
            
            tasks = []
            if run_summary:
                tasks.append(self.summary_chain.ainvoke({
                    "old_summary": current_summary,
                    "new_messages": batch_history_str,
                }, config={"run_name": "Update Session Summary Chain"}))
            else:
                tasks.append(asyncio.sleep(0))
                
            if run_persona:
                tasks.append(self.persona_chain.ainvoke({
                    "user_persona": current_persona,
                    "messages_history": batch_history_str,
                    "user_query": user_query,
                }, config={"run_name": "Update Student Persona Chain"}))
            else:
                tasks.append(asyncio.sleep(0))
            
            new_summary, persona_decision = await asyncio.gather(*tasks)
            
            collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
            if collection:
                if run_summary and new_summary:
                    collection.summary = new_summary
                    collection.unsummarized_count = 0
                if run_persona and persona_decision and persona_decision.should_update and persona_decision.updated_persona:
                    collection.persona = persona_decision.updated_persona
                await self.redis_provider.save_collection(collection, session_id=session_id)
                logger.info("Background update for persona/summary completed successfully.")
        except Exception as exc:
            logger.error("Failed background update for persona and summary: %s", exc, exc_info=True)


    async def _push_evaluation(
        self,
        user_query: str,
        context: str,
        answer: str,
        student_id: str,
        session_id: str,
        run_step_outputs: list = None,
        persona: str = None,
        summary: str = None,
        llm_usage: dict = None,
        llm_metadata: dict = None,
        llm_usage_breakdown: dict = None,
        latency_ms: float = None,
    ) -> None:
        try:
            resolved_model = (
                (llm_metadata.get("model") if llm_metadata else None)
                or self.generation_model_id
            )

            doc = EvaluationModel(
                request=RequestLayer(
                    user_query=user_query,
                    session_id=session_id,
                    student_id=student_id,
                    context_data={"persona": persona, "summary": summary},
                ),
                retrieval=RetrievalLayer(
                    final_context=context,
                    raw_documents=[
                        s.model_dump() if hasattr(s, "model_dump") else s
                        for s in (run_step_outputs or [])
                    ],
                ),
                generation=GenerationLayer(
                    final_answer=answer,
                    parameters={
                        "model":       resolved_model,
                        "temperature": 0.7,
                    },
                    metadata={
                        "finish_reason":      llm_metadata.get("finish_reason")      if llm_metadata else None,
                        "system_fingerprint": llm_metadata.get("system_fingerprint") if llm_metadata else None,
                    },
                ),
                performance=PerformanceLayer(
                    latency_ms=latency_ms,
                    token_usage=llm_usage or {},
                    metrics={"llm_usage_breakdown": llm_usage_breakdown or {}},
                ),
            )
            await self.evaluation_repo.add_eval_session(doc)
            logger.info("Evaluation session pushed to MongoDB.")
        except Exception as exc:
            logger.warning("Failed to push evaluation session to MongoDB: %s", exc)


    async def delete_student_persona(self, user_id: str) -> DeletePersonaResponse:

        user_id = (user_id or "").strip()
        if not user_id:
            raise ChatbotValidationError(
                message="User ID is required.",
                details={"user_id": user_id}
            )

        logger.info("Persona deletion request initiated for user: %s", user_id)

        try:
            has_active = await self.redis_provider.has_active_sessions(user_id)
            if has_active:
                raise ProcessingError(
                    message=(
                        f"Cannot delete persona for user '{user_id}' because there are active sessions running in Redis. "
                        "Please end all active sessions first using the session router, then try again."
                    ),
                    details={"user_id": user_id, "reason": "active_sessions_exist"},
                )

            persona_doc = await self.student_persona_repo.get_persona_by_student_id(user_id)
            if persona_doc is None:
                raise NotFoundError(
                    message=f"No persona found for user '{user_id}' to delete.",
                    details={"user_id": user_id},
                )

            deleted = await self.student_persona_repo.delete_persona(user_id)
            if not deleted:
                raise ProcessingError(
                    message=f"Failed to delete persona for user '{user_id}'.",
                    details={"user_id": user_id},
                )

            logger.info("Successfully deleted persona for user: %s", user_id)
            return DeletePersonaResponse(
                user_id=user_id,
                deleted=True,
                message=f"Persona for user '{user_id}' has been successfully deleted."
            )

        except (NotFoundError, ProcessingError, ChatbotValidationError):
            raise
        except Exception as exc:
            logger.exception("Unexpected error while deleting persona for user %s", user_id)
            raise ProcessingError(
                message="An unexpected error occurred during persona deletion.",
                details={"user_id": user_id, "error": str(exc)},
            ) from exc

