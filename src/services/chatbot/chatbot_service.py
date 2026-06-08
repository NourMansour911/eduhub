import asyncio
import json
from typing import Any
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

from services.chatbot.agents.rag.retrieving.sql.sql_server_calling import SqlServerCalling

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

    async def chat(self, payload: ChatRequest, student_id: str, session_id: str) -> ChatResponse:
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

        if not collection.student_courses:
            logger.info("student_courses not found in Redis, retrieving from SQL server for student_id: %s", student_id)
            try:
                courses = self.sql_tools.sql_server_calling.get_student_courses(student_id)
            except Exception as exc:
                raise ChatbotExternalError(
                    message="Failed to retrieve student courses from SQL",
                    details={"student_id": student_id, "error": str(exc)},
                ) from exc
            courses_str = ", ".join([f"{c.get('name', 'Unknown')}(ID:{c.get('course_id', 'Unknown')})" for c in courses])
            collection.student_courses = courses_str
            logger.info("Cached formatted student_courses: %s", courses_str)
        else:
            logger.info("Using cached student_courses from Redis: %s", collection.student_courses)

        previous_steps_outputs = collection.contexts[-3:]
        logger.info("Retrieved last %d turns of step outputs.", len(previous_steps_outputs))

        raw_history = collection.messages or []
        last_4_messages = []
        for msg in raw_history[-4:]:
            role = "Human" if msg.get("role") == "user" else "AI"
            last_4_messages.append({"role": role, "content": msg.get("content", "")})
        logger.info("Formatted last 4 messages of chat history: %s", last_4_messages)

        try:
            graph_result = await self.chatbot_graph.ainvoke({
                "user_query": payload.message,
                "student_id": student_id,
                "session_id": session_id,
                "student_courses": collection.student_courses,
                "messages_history": last_4_messages,
                "user_persona": collection.persona,
                "session_summary": collection.summary,
                "previous_steps_outputs": previous_steps_outputs,
            })
        except Exception as exc:
            raise ChatbotProcessingError(
                message="Chatbot graph execution failed",
                details={"student_id": student_id, "session_id": session_id, "error": str(exc)},
            ) from exc

        ai_reply = graph_result.get("response") or "I'm sorry, I could not generate a response."
        logger.info("Chatbot graph result response: %s", ai_reply)

        collection.messages.append({"role": "user", "content": payload.message})
        collection.messages.append({"role": "assistant", "content": ai_reply})
        collection.persona = graph_result.get("user_persona")
        collection.summary = graph_result.get("session_summary")

        run_step_outputs = graph_result.get("run_step_outputs") or []
        collection.contexts.append(run_step_outputs)

        await self.redis_provider.save_collection(collection, session_id=session_id)
        logger.info(
            "Redis session collection saved. Current Redis State:\n%s",
            json.dumps(collection.model_dump(), indent=2, ensure_ascii=False, default=str),
        )

        asyncio.create_task(self._push_llm_judge(
            user_query=payload.message,
            context=graph_result.get("retrieved_context") or "",
            answer=ai_reply,
        ))

        return ChatResponse(ai_response=ai_reply)

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
