import asyncio
from langchain_core.runnables import Runnable

from fastapi import Depends

from core import Settings, get_settings
from helpers import get_logger
from core.request_dependencies import (
    get_langchain_client,
    get_llm_judge_repo,
    get_redis_provider,
    get_student_persona_repo,
)
from integrations import RedisProvider
from integrations.llm import LCOpenAI
from models import LLMJudgeInputModel
from repositories import LLMJudgeRepo, StudentPersonaRepo
from schemas import ChatRequest, ChatResponse
from dtos.redis_session_dto import RedisSessionDTO

from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools, get_vdb_tools
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools, get_mongodb_tools
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools, get_sql_tools

from .agents.rag import build_rag_subgraph
from .builder import build_chatbot_graph
from .chatbot_exceptions import ChatbotExternalError, ChatbotProcessingError, ChatbotValidationError

logger = get_logger(__name__)


class ChatbotService:
    def __init__(
        self,
        lc_openai_client: LCOpenAI,
        settings: Settings,
        vdb_tools: VDBTools,
        mongodb_tools: MongoDBTools,
        sql_tools: SQLTools,
        student_persona_repo: StudentPersonaRepo,
        redis_provider: RedisProvider,
        llm_judge_repo: LLMJudgeRepo,
    ) -> None:
        self.sql_tools = sql_tools
        self.redis_provider = redis_provider
        self.llm_judge_repo = llm_judge_repo

        llm_map = {
            # Routing decision — must be deterministic
            "orchestrator": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.0
            ),
            # Luma tutor — conversational, needs warmth and natural language variation
            "answering": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.7
            ),
            # Incremental summary merge — factual, must not hallucinate
            "summary": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.2
            ),
            # Persona classifier — structured output, semi-deterministic
            "persona": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.1
            ),
        }

        self.rag_subgraph = build_rag_subgraph(
            lc_openai_client=lc_openai_client,
            settings=settings,
            vdb_tools=vdb_tools,
            mongodb_tools=mongodb_tools,
            sql_tools=sql_tools,
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

        logger.debug("Chatbot session run initiated. student_id: %s | session_id: %s", student_id, session_id)

        collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
        if collection is None:
            collection = RedisSessionDTO(user_id=student_id)

        if not collection.student_courses:
            logger.debug("student_courses not found in Redis, retrieving from SQL server for student_id: %s", student_id)
            try:
                courses = self.sql_tools.sql_server_calling.get_student_courses(student_id)
            except Exception as exc:
                raise ChatbotExternalError(
                    message="Failed to retrieve student courses from SQL",
                    details={"student_id": student_id, "error": str(exc)},
                ) from exc
            courses_str = ", ".join([f"{c.get('name', 'Unknown')}(ID:{c.get('course_id', 'Unknown')})" for c in courses])
            collection.student_courses = courses_str
            logger.debug("Cached formatted student_courses: %s", courses_str)
        else:
            logger.debug("Using cached student_courses from Redis: %s", collection.student_courses)

        previous_steps_outputs = collection.contexts[-3:]
        logger.debug("Retrieved last %d turns of step outputs.", len(previous_steps_outputs))

        raw_history = collection.messages or []
        last_4_messages = []
        for msg in raw_history[-4:]:
            role = "Human" if msg.get("role") == "user" else "AI"
            last_4_messages.append({"role": role, "content": msg.get("content", "")})
        logger.debug("Formatted last 4 messages of chat history: %s", last_4_messages)

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
        logger.debug("Chatbot graph result response: %s", ai_reply)

        collection.messages.append({"role": "user", "content": payload.message})
        collection.messages.append({"role": "assistant", "content": ai_reply})
        collection.persona = graph_result.get("user_persona")

        run_step_outputs = graph_result.get("run_step_outputs") or []
        collection.contexts.append(run_step_outputs)

        collection.summary = graph_result.get("session_summary")

        await self.redis_provider.save_collection(collection, session_id=session_id)
        logger.debug("Redis session collection saved.")

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
            logger.debug("LLM judge sample pushed to MongoDB.")
        except Exception as exc:
            logger.warning("Failed to push LLM judge sample to MongoDB: %s", exc)


def get_chatbot_service(
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
    settings: Settings = Depends(get_settings),
    vdb_tools: VDBTools = Depends(get_vdb_tools),
    mongodb_tools: MongoDBTools = Depends(get_mongodb_tools),
    sql_tools: SQLTools = Depends(get_sql_tools),
    student_persona_repo: StudentPersonaRepo = Depends(get_student_persona_repo),
    redis_provider: RedisProvider = Depends(get_redis_provider),
    llm_judge_repo: LLMJudgeRepo = Depends(get_llm_judge_repo),
) -> ChatbotService:
    return ChatbotService(
        lc_openai_client=lc_openai_client,
        settings=settings,
        vdb_tools=vdb_tools,
        mongodb_tools=mongodb_tools,
        sql_tools=sql_tools,
        student_persona_repo=student_persona_repo,
        redis_provider=redis_provider,
        llm_judge_repo=llm_judge_repo,
    )
