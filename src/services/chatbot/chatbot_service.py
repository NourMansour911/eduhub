import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from langchain_core.runnables import Runnable

from core import Settings
from dtos.redis_session_dto import RedisSessionDTO
from helpers.logger import get_chatbot_logger
from integrations.litellm_admin import LiteLLMAdminClient
from integrations.llm import LCOpenAI, PromptRegistry
from integrations.redis_provider import RedisProvider
from repositories.evaluation_repo import EvaluationRepo
from repositories.student_persona_repo import StudentPersonaRepo
from schemas import ChatRequest, ChatResponse
from schemas.assistant_schema import DeletePersonaResponse
from services.chatbot.agents.rag.builder import build_rag_subgraph
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools
from services.chatbot.agents.rag.retrieving.sql.sql_server_calling import SqlServerCalling
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools
from services.chatbot.agents.rag.retrieving.vdb.search_service import SearchService
from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools
from services.chatbot.builder import build_chatbot_graph
from services.chatbot.chains.persona_chain import build_persona_chain
from services.chatbot.chains.summary_chain import build_summary_chain
from services.chatbot.chatbot_exceptions import ChatbotProcessingError, ChatbotValidationError
from services.chatbot.post_processor import ChatPostProcessor
from services.chatbot.preflight import ChatContext, ChatPreflightHandler
from services.chatbot.rate_limiter import UserRateLimiter
from services.chatbot.security.guardrail_pipeline import GuardrailPipeline
from services.lectures.lecture_service import LectureService
from services.service_exceptions import NotFoundError, ProcessingError
from services.session.session_exceptions import SessionNotFoundError
from services.summarize.summarize_service import SummarizeService

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
        prompt_registry: Optional[PromptRegistry] = None,
        guardrail_pipeline: Optional[GuardrailPipeline] = None,
        rate_limiter: Optional[UserRateLimiter] = None,
        litellm_admin: Optional[LiteLLMAdminClient] = None,
    ) -> None:
        sql_server_calling = SqlServerCalling(base_url=settings.DB_BASE_URL)
        self.sql_tools = SQLTools(embedding_client=embedding_client, sql_server_calling=sql_server_calling)
        self.redis_provider = redis_provider
        self.rate_limiter = rate_limiter or UserRateLimiter(redis_provider=redis_provider)
        self.litellm_admin = litellm_admin
        self.evaluation_repo = evaluation_repo
        self.student_persona_repo = student_persona_repo
        self.prompt_registry = prompt_registry
        self.guardrail_pipeline = guardrail_pipeline

        
        self._init_graph_and_chains(
            lc_openai_client=lc_openai_client,
            settings=settings,
            vdb_client=vdb_client,
            embedding_client=embedding_client,
            lecture_service=lecture_service,
            summarize_service=summarize_service,
        )

       
        self.preflight = ChatPreflightHandler(
            redis_provider=self.redis_provider,
            rate_limiter=self.rate_limiter,
            sql_tools=self.sql_tools,
            guardrail_pipeline=self.guardrail_pipeline,
            litellm_admin=self.litellm_admin,
        )
        self.post_processor = ChatPostProcessor(
            redis_provider=self.redis_provider,
            evaluation_repo=self.evaluation_repo,
            summary_chain=self.summary_chain,
            persona_chain=self.persona_chain,
        )

    def _init_graph_and_chains(
        self,
        lc_openai_client: LCOpenAI,
        settings: Settings,
        vdb_client: Any,
        embedding_client: Any,
        lecture_service: LectureService,
        summarize_service: SummarizeService,
    ) -> None:
        prompt_map = {}
        if self.prompt_registry:
            prompt_map = {
                "orchestrator": self.prompt_registry.get("orchestrator"),
                "answering": self.prompt_registry.get("answering"),
                "planner": self.prompt_registry.get("planner"),
                "reflection": self.prompt_registry.get("reflection"),
            }

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
                model=settings.get_model_for("orchestrator"), temperature=0.0
            ),
            "answering": lc_openai_client.get_langchain_llm(
                model=settings.get_model_for("answering"), temperature=0.7
            ),
            "answering_free": lc_openai_client.get_langchain_llm(
                model="eduhub/answering-free", temperature=0.7
            ),
            "answering_standard": lc_openai_client.get_langchain_llm(
                model="eduhub/answering", temperature=0.7
            ),
            "answering_premium": lc_openai_client.get_langchain_llm(
                model="eduhub/answering-premium", temperature=0.7
            ),
            "summary": lc_openai_client.get_langchain_llm(
                model=settings.get_model_for("summary"), temperature=0.2
            ),
            "persona": lc_openai_client.get_langchain_llm(
                model=settings.get_model_for("persona"), temperature=0.1
            ),
        }

        self.rag_subgraph = build_rag_subgraph(
            lc_openai_client=lc_openai_client,
            settings=settings,
            vdb_tools=vdb_tools,
            mongodb_tools=mongodb_tools,
            sql_tools=self.sql_tools,
            redis_provider=self.redis_provider,
            prompt_map=prompt_map,
        )
        self.chatbot_graph: Runnable = build_chatbot_graph(
            llm_map=llm_map,
            rag_subgraph=self.rag_subgraph,
            redis_provider=self.redis_provider,
            prompt_map=prompt_map,
        )
        self.summary_chain = build_summary_chain(
            llm_map["summary"],
            prompt=self.prompt_registry.get("session-summary") if self.prompt_registry else None,
        )
        self.persona_chain = build_persona_chain(
            llm_map["persona"],
            prompt=self.prompt_registry.get("persona") if self.prompt_registry else None,
        )
        self.generation_model_id = settings.GENERATION_MODEL_ID

    async def chat(self, payload: ChatRequest, student_id: str, session_id: str) -> ChatResponse:
        
        ctx = await self.preflight.prepare_context(
            student_id=student_id,
            session_id=session_id,
            user_query=payload.message or "",
        )

        if ctx.is_guardrail_blocked:
            return ChatResponse(ai_response=ctx.guardrail_response)

        try:
            _t0 = time.perf_counter()
            graph_result = await self.chatbot_graph.ainvoke(
                ctx.graph_input, config={"run_name": "Chatbot Graph Run"}
            )
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

        
        await self.post_processor.process(
            ctx=ctx,
            ai_reply=cleaned_reply,
            graph_result=graph_result,
            latency_ms=latency_ms,
        )

        return response_obj

    async def chat_stream(
        self, payload: ChatRequest, student_id: str, session_id: str
    ) -> AsyncGenerator[str, None]:
       
        try:
            ctx = await self.preflight.prepare_context(
                student_id=student_id,
                session_id=session_id,
                user_query=payload.message or "",
            )
        except ChatbotValidationError as exc:
            yield self._format_sse_error(exc)
            return
        except SessionNotFoundError as exc:
            yield f"data: {json.dumps({'error': exc.message}, ensure_ascii=False)}\n\n"
            return

        if ctx.is_guardrail_blocked:
            blocked_reply = ctx.guardrail_response or "I cannot process this request due to safety policies."
            yield f"data: {json.dumps({'token': blocked_reply}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True, 'full_response': blocked_reply}, ensure_ascii=False)}\n\n"
            return

        accumulated_text = ""
        graph_final_state: Dict[str, Any] = {}
        _t0 = time.perf_counter()

        try:
            async for event in self.chatbot_graph.astream_events(
                ctx.graph_input,
                config={"run_name": "Chatbot Graph Run"},
                version="v2",
            ):
                event_type = event.get("event")
                if event_type == "on_chat_model_stream":
                    node_name = event.get("metadata", {}).get("langgraph_node")
                    if node_name == "answering" or "Answering LLM" in event.get("name", ""):
                        chunk = event.get("data", {}).get("chunk")
                        token = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if token:
                            accumulated_text += token
                            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

                elif event_type == "on_chain_end":
                    chain_name = event.get("name")
                    if chain_name in ("ChatbotGraph", "LangGraph", "chatbot_graph"):
                        output = event.get("data", {}).get("output")
                        if isinstance(output, dict):
                            graph_final_state = output

        except Exception as exc:
            logger.exception("Error during graph stream execution")
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
            return

        latency_ms = round((time.perf_counter() - _t0) * 1000, 2)

        if not accumulated_text and graph_final_state.get("response"):
            fallback_resp = graph_final_state.get("response")
            accumulated_text = fallback_resp
            yield f"data: {json.dumps({'token': fallback_resp}, ensure_ascii=False)}\n\n"

        if not accumulated_text:
            accumulated_text = "I'm sorry, I could not generate a response."
            yield f"data: {json.dumps({'token': accumulated_text}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'done': True, 'full_response': accumulated_text}, ensure_ascii=False)}\n\n"

       
        try:
            await self.post_processor.process(
                ctx=ctx,
                ai_reply=accumulated_text,
                graph_result=graph_final_state,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error("Error during post-stream cleanup: %s", exc)

    @staticmethod
    def _format_sse_error(exc: ChatbotValidationError) -> str:
       
        payload: Dict[str, Any] = {"error": exc.message}
        if exc.details:
            if "rpm_limit" in exc.details or "daily_limit" in exc.details:
                payload["code"] = 429
                payload.update(exc.details)
            elif exc.details.get("reason") == "monthly_budget_exhausted":
                payload["code"] = 402
                payload.update(exc.details)
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


    async def _get_and_cache_student_courses(self, student_id: str, collection: RedisSessionDTO) -> str:
        return await self.preflight.get_and_cache_student_courses(student_id, collection)

    def _update_session_contexts(self, collection: RedisSessionDTO, run_step_outputs: List[Any]) -> None:
        self.post_processor.update_session_contexts(collection, run_step_outputs)

    async def _push_evaluation(self, **kwargs: Any) -> None:
        await self.post_processor.push_evaluation(**kwargs)

    async def _update_persona_and_summary_background(self, **kwargs: Any) -> None:
        await self.post_processor.update_persona_and_summary_background(**kwargs)

    async def delete_student_persona(self, user_id: str) -> DeletePersonaResponse:
       
        user_id = (user_id or "").strip()
        if not user_id:
            raise ChatbotValidationError(
                message="User ID is required.",
                details={"user_id": user_id},
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
                message=f"Persona for user '{user_id}' has been successfully deleted.",
            )

        except (NotFoundError, ProcessingError, ChatbotValidationError):
            raise
        except Exception as exc:
            logger.exception("Unexpected error while deleting persona for user %s", user_id)
            raise ProcessingError(
                message="An unexpected error occurred during persona deletion.",
                details={"user_id": user_id, "error": str(exc)},
            ) from exc
