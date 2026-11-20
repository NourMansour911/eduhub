import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from core.plans import get_user_plan_config
from dtos.redis_session_dto import RedisSessionDTO
from helpers.logger import get_chatbot_logger
from integrations.litellm_admin import LiteLLMAdminClient
from integrations.redis_provider import RedisProvider
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools
from services.chatbot.chatbot_exceptions import ChatbotValidationError
from services.chatbot.rate_limiter import UserRateLimiter
from services.chatbot.security.guardrail_pipeline import GuardrailPipeline
from services.chatbot.utils import format_chat_history_for_graph, format_student_courses
from services.session.session_exceptions import SessionNotFoundError

logger = get_chatbot_logger(__name__)


@dataclass
class ChatContext:
    student_id: str
    session_id: str
    user_query: str
    student_plan: str
    collection: RedisSessionDTO
    graph_input: Dict[str, Any] = field(default_factory=dict)
    is_guardrail_blocked: bool = False
    guardrail_response: Optional[str] = None
    guardrail_action: Optional[str] = None
    guardrail_violation_type: Optional[str] = None
    guardrail_score: float = 0.0


class ChatPreflightHandler:
    def __init__(
        self,
        redis_provider: RedisProvider,
        rate_limiter: UserRateLimiter,
        sql_tools: SQLTools,
        guardrail_pipeline: Optional[GuardrailPipeline] = None,
        litellm_admin: Optional[LiteLLMAdminClient] = None,
    ) -> None:
        self.redis_provider = redis_provider
        self.rate_limiter = rate_limiter
        self.sql_tools = sql_tools
        self.guardrail_pipeline = guardrail_pipeline
        self.litellm_admin = litellm_admin

    def validate_inputs(self, student_id: str, session_id: str, user_query: str) -> Tuple[str, str, str]:
        user_query = (user_query or "").strip()
        query_len = len(user_query)
        if query_len > 1000:
            raise ChatbotValidationError(
                message=f"Query is too long ({query_len} characters). Maximum allowed length is 1000 characters.",
                details={"query_len": query_len, "max_limit": 1000},
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

        return student_id, session_id, user_query

    async def get_and_validate_session(self, student_id: str, session_id: str) -> RedisSessionDTO:
        collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
        if collection is None:
            raise SessionNotFoundError(
                message="Active session not found. Please start a session before chatting.",
                details={"student_id": student_id, "session_id": session_id},
            )
        return collection

    async def check_rate_limits(self, student_id: str, collection: RedisSessionDTO) -> str:
        student_plan = getattr(collection, "plan", "free") or "free"
        plan_config = get_user_plan_config(student_plan)

        is_allowed, reason, meta = await self.rate_limiter.check_and_increment(
            student_id=student_id,
            rpm_limit=plan_config.rpm,
            daily_limit=plan_config.daily_limit,
        )
        if not is_allowed:
            raise ChatbotValidationError(
                message=reason,
                details={"student_id": student_id, "plan": student_plan, **meta},
            )
        return student_plan

    async def check_budget(self, student_id: str, student_plan: str) -> None:
        if self.litellm_admin:
            has_budget, current_spend, max_b = await self.litellm_admin.check_user_budget(student_id)
            if not has_budget:
                logger.warning(
                    "ChatPreflightHandler: Pre-flight budget check failed for student '%s'. Spend=$%.4f >= Max=$%.2f.",
                    student_id,
                    current_spend,
                    max_b,
                )
                raise ChatbotValidationError(
                    message=f"You have exhausted your monthly plan budget (${current_spend:.2f} of ${max_b:.2f}). Please upgrade your plan to continue.",
                    details={
                        "student_id": student_id,
                        "spend": current_spend,
                        "max_budget": max_b,
                        "plan": student_plan,
                        "reason": "monthly_budget_exhausted",
                    },
                )

    async def evaluate_guardrails(
        self, user_query: str, collection: RedisSessionDTO, session_id: str
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str], float]:
        if self.guardrail_pipeline is not None:
            guardrail_decision = await self.guardrail_pipeline.evaluate(user_query)
            if guardrail_decision.is_blocked:
                ai_reply = guardrail_decision.response_text or "I cannot process this request due to safety policies."

                collection.messages.append({"role": "user", "content": user_query})
                collection.messages.append({"role": "assistant", "content": ai_reply})
                await self.redis_provider.save_collection(collection, session_id=session_id)

                logger.info(
                    "ChatPreflightHandler: Query short-circuited by GuardrailPipeline (action=%s).",
                    guardrail_decision.action,
                )
                return (
                    True,
                    ai_reply,
                    guardrail_decision.action,
                    guardrail_decision.violation_type,
                    guardrail_decision.score,
                )
        return False, None, None, None, 0.0

    async def get_and_cache_student_courses(self, student_id: str, collection: RedisSessionDTO) -> str:
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

    async def prepare_context(self, student_id: str, session_id: str, user_query: str) -> ChatContext:
        valid_student_id, valid_session_id, valid_query = self.validate_inputs(student_id, session_id, user_query)
        logger.info(
            "Chatbot session pre-flight initiated. student_id: %s | session_id: %s",
            valid_student_id,
            valid_session_id,
        )

        collection = await self.get_and_validate_session(valid_student_id, valid_session_id)
        student_plan = await self.check_rate_limits(valid_student_id, collection)
        await self.check_budget(valid_student_id, student_plan)

        is_blocked, guardrail_reply, action, violation_type, score = await self.evaluate_guardrails(
            valid_query, collection, valid_session_id
        )
        if is_blocked:
            return ChatContext(
                student_id=valid_student_id,
                session_id=valid_session_id,
                user_query=valid_query,
                student_plan=student_plan,
                collection=collection,
                is_guardrail_blocked=True,
                guardrail_response=guardrail_reply,
                guardrail_action=action,
                guardrail_violation_type=violation_type,
                guardrail_score=score,
            )

        student_courses = await self.get_and_cache_student_courses(valid_student_id, collection)
        last_messages = format_chat_history_for_graph(collection.messages or [], limit=6)
        logger.info("Formatted last messages of chat history: %s", last_messages)

        graph_input = {
            "user_query": valid_query,
            "student_id": valid_student_id,
            "session_id": valid_session_id,
            "user_plan": student_plan,
            "student_courses": student_courses,
            "messages_history": last_messages,
            "user_persona": collection.persona,
            "session_summary": collection.summary,
        }

        return ChatContext(
            student_id=valid_student_id,
            session_id=valid_session_id,
            user_query=valid_query,
            student_plan=student_plan,
            collection=collection,
            graph_input=graph_input,
            is_guardrail_blocked=False,
            guardrail_response=None,
        )
