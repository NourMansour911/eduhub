import asyncio
import json
from typing import Any, List, Dict
from langchain_core.runnables import Runnable

from core import Settings
from helpers.logger import get_chatbot_logger
from integrations.redis_provider import RedisProvider
from integrations.llm import LCOpenAI
from models import LLMJudgeInputModel
from repositories.llm_judge_repo import LLMJudgeRepo
from schemas import ChatRequest, ChatResponse
from dtos.redis_session_dto import RedisSessionDTO

from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools
from services.chatbot.agents.rag.retrieving.vdb.search_service import SearchService
from services.lectures.lecture_service import LectureService
from services.summarize.summarize_service import SummarizeService

from .agents.rag.builder import build_rag_subgraph
from .builder import build_chatbot_graph
from .chatbot_exceptions import ChatbotExternalError, ChatbotProcessingError, ChatbotValidationError
from .chains.summary_chain import build_summary_chain
from .chains.persona_chain import build_persona_chain

from services.chatbot.agents.rag.retrieving.sql.sql_server_calling import SqlServerCalling
from services.chatbot.utils import format_student_courses, format_chat_history_for_graph, deduplicate_tool_outputs

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
        llm_judge_repo: LLMJudgeRepo,
    ) -> None:
        sql_server_calling = SqlServerCalling(base_url=settings.DB_BASE_URL)
        self.sql_tools = SQLTools(embedding_client=embedding_client, sql_server_calling=sql_server_calling)
        self.redis_provider = redis_provider
        self.llm_judge_repo = llm_judge_repo

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
                model=settings.GENERATION_MODEL_ID, temperature=0.0, max_tokens=150
            ),
            "answering": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.7, max_tokens=1500
            ),
            "summary": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.2, max_tokens=300
            ),
            "persona": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.1, max_tokens=250
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
            collection = RedisSessionDTO(user_id=student_id)

        student_courses = await self._get_and_cache_student_courses(student_id, collection)

        
        raw_past = collection.contexts[-3:] if collection.contexts else []
        flattened_past = []
        for turn in raw_past:
            if isinstance(turn, list):
                flattened_past.extend(turn)
            else:
                flattened_past.append(turn)

        past_messages_tool_outputs = deduplicate_tool_outputs(flattened_past)

        logger.info("Retrieved last %d turns of step outputs. Flattened/deduplicated to %d past outputs.", len(raw_past), len(past_messages_tool_outputs))

        last_messages = format_chat_history_for_graph(collection.messages or [], limit=6)
        logger.info("Formatted last messages of chat history: %s", last_messages)

        try:
            graph_result = await self.chatbot_graph.ainvoke({
                "user_query": user_query,
                "student_id": student_id,
                "session_id": session_id,
                "student_courses": student_courses,
                "messages_history": last_messages,
                "user_persona": collection.persona,
                "session_summary": collection.summary,
                "past_messages_tool_outputs": past_messages_tool_outputs,
            })
        except Exception as exc:
            raise ChatbotProcessingError(
                message="Chatbot graph execution failed",
                details={"student_id": student_id, "session_id": session_id, "error": str(exc)},
            ) from exc

        ai_reply = graph_result.get("response") or "I'm sorry, I could not generate a response."
        logger.info("Chatbot graph result response: %s", ai_reply)

        collection.messages.append({"role": "user", "content": user_query})
        collection.messages.append({"role": "assistant", "content": ai_reply})

        run_step_outputs = graph_result.get("run_step_outputs") or []
        self._update_session_contexts(collection, run_step_outputs)

        await self.redis_provider.save_collection(collection, session_id=session_id)
        logger.info(
            "Redis session collection saved. Current Redis State:\n%s",
            json.dumps(collection.model_dump(), indent=2, ensure_ascii=False, default=str),
        )

        asyncio.create_task(self._push_llm_judge(
            user_query=user_query,
            context=graph_result.get("retrieved_context") or "",
            answer=ai_reply,
        ))

        needs_persona_update = graph_result.get("needs_persona_update", False)
        needs_summary_update = graph_result.get("needs_summary_update", False)

        if needs_persona_update or needs_summary_update:
            batch_history_str = ""
            for msg in collection.messages[-8:]:
                role = "User" if msg.get("role") == "user" else "AI"
                batch_history_str += f"{role}: {msg.get('content', '')}\n"

            asyncio.create_task(self._update_persona_and_summary_background(
                student_id=student_id,
                session_id=session_id,
                user_query=user_query,
                batch_history_str=batch_history_str,
                current_persona=collection.persona,
                current_summary=collection.summary,
                run_persona=needs_persona_update,
                run_summary=needs_summary_update
            ))

        return ChatResponse(ai_response=ai_reply)

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
                }))
            else:
                tasks.append(asyncio.sleep(0))
                
            if run_persona:
                tasks.append(self.persona_chain.ainvoke({
                    "user_persona": current_persona,
                    "messages_history": batch_history_str,
                    "user_query": user_query,
                }))
            else:
                tasks.append(asyncio.sleep(0))
            
            new_summary, persona_decision = await asyncio.gather(*tasks)
            
            collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
            if collection:
                if run_summary and new_summary:
                    collection.summary = new_summary
                if run_persona and persona_decision and persona_decision.should_update and persona_decision.updated_persona:
                    collection.persona = persona_decision.updated_persona
                await self.redis_provider.save_collection(collection, session_id=session_id)
                logger.info("Background update for persona/summary completed successfully.")
        except Exception as exc:
            logger.error("Failed background update for persona and summary: %s", exc, exc_info=True)

    async def _push_llm_judge(self, user_query: str, context: str, answer: str) -> None:
        try:
            doc = LLMJudgeInputModel(
                user_query=user_query,
                context=context,
                answer=answer,
            )
            await self.llm_judge_repo.add_judge_input(doc)
            logger.info("LLM judge sample pushed to MongoDB.")
        except Exception as exc:
            logger.warning("Failed to push LLM judge sample to MongoDB: %s", exc)
