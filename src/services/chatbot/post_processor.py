import asyncio
import json
from typing import Any, Dict, List, Optional
from langchain_core.runnables import Runnable

from dtos.redis_session_dto import RedisSessionDTO
from helpers.logger import get_chatbot_logger
from integrations.redis_provider import RedisProvider
from models import EvaluationModel
from models.evaluation_model import (
    EvaluationMetricsLayer,
    GenerationLayer,
    PerformanceLayer,
    RequestLayer,
    RetrievalLayer,
)
from repositories.evaluation_repo import EvaluationRepo
from services.chatbot.utils import clip_message_content
from .preflight import ChatContext

logger = get_chatbot_logger(__name__)

MODEL_PRICING_PER_1M: Dict[str, tuple[float, float]] = {
    "openrouter/deepseek/deepseek-v4-flash": (0.14, 0.28),
    "deepseek/deepseek-v4-flash": (0.14, 0.28),
    "eduhub/router": (0.14, 0.28),
    "eduhub/answering": (0.14, 0.28),
    "eduhub/answering-free": (0.14, 0.28),
    "eduhub/answering-premium": (0.14, 0.28),
    "eduhub/planner": (0.14, 0.28),
    "eduhub/reflection": (0.14, 0.28),
    "eduhub/summary": (0.14, 0.28),
    "eduhub/persona": (0.14, 0.28),
    "eduhub/grading": (0.14, 0.28),
    "eduhub/rewriter": (0.14, 0.28),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "default": (0.15, 0.30),
}


def calculate_llm_cost(token_usage_tree: Dict[str, Any]) -> float:
    if not isinstance(token_usage_tree, dict):
        return 0.0

    total_cost = 0.0
    for node_name, node_data in token_usage_tree.items():
        if node_name == "total" or not isinstance(node_data, dict):
            continue

        usage = node_data.get("usage") or {}
        metadata = node_data.get("metadata") or {}
        model_name = metadata.get("model") or "default"

        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0

        pricing = MODEL_PRICING_PER_1M.get(model_name, MODEL_PRICING_PER_1M["default"])
        node_cost = (prompt_tokens * pricing[0] + completion_tokens * pricing[1]) / 1_000_000.0
        total_cost += node_cost

    return round(total_cost, 6)


class ChatPostProcessor:
    def __init__(
        self,
        redis_provider: RedisProvider,
        evaluation_repo: EvaluationRepo,
        summary_chain: Runnable,
        persona_chain: Runnable,
    ) -> None:
        self.redis_provider = redis_provider
        self.evaluation_repo = evaluation_repo
        self.summary_chain = summary_chain
        self.persona_chain = persona_chain

    def update_session_contexts(self, collection: RedisSessionDTO, run_step_outputs: List[Any]) -> None:
        if run_step_outputs:
            collection.contexts.append(run_step_outputs)
            logger.debug("Appended %d run step outputs to Redis session contexts.", len(run_step_outputs))

    async def save_session_turn(
        self,
        collection: RedisSessionDTO,
        session_id: str,
        user_query: str,
        ai_reply: str,
        run_step_outputs: List[Any],
    ) -> None:
        collection.messages.append({"role": "user", "content": user_query})
        collection.messages.append({"role": "assistant", "content": ai_reply})
        self.update_session_contexts(collection, run_step_outputs)
        await self.redis_provider.save_collection(collection, session_id=session_id)
        logger.info(
            "Redis session collection saved. Current Redis State:\n%s",
            json.dumps(collection.model_dump(), indent=2, ensure_ascii=False, default=str),
        )

    async def push_evaluation(
        self,
        user_query: str,
        context: str,
        answer: str,
        student_id: str,
        session_id: str,
        run_step_outputs: Optional[List[Any]] = None,
        persona: Optional[str] = None,
        summary: Optional[str] = None,
        llm_usage_breakdown: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        try:
            retrieval_config: Dict[str, Any] = {}
            if run_step_outputs:
                tools_used = [
                    getattr(s, "tool_name", "") if hasattr(s, "tool_name") else s.get("tool_name", "")
                    for s in run_step_outputs
                ]
                sources = list(
                    set(
                        getattr(s, "source", "") if hasattr(s, "source") else s.get("source", "")
                        for s in run_step_outputs
                    )
                )
                retrieval_config = {
                    "tools_used": [t for t in tools_used if t],
                    "sources": [s for s in sources if s],
                    "steps_count": len(run_step_outputs),
                    "search_strategy": "multi_source_dag_rag",
                }

            calculated_cost = calculate_llm_cost(llm_usage_breakdown or {})

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
                    config=retrieval_config,
                ),
                generation=GenerationLayer(
                    final_answer=answer,
                ),
                performance=PerformanceLayer(
                    latency_ms=latency_ms,
                    token_usage=llm_usage_breakdown or {},
                    cost=calculated_cost,
                ),
            )
            await self.evaluation_repo.add_eval_session(doc)
            logger.info("Evaluation session pushed to MongoDB (cost=$%.6f USD).", calculated_cost)
        except Exception as exc:
            logger.warning("Failed to push evaluation session to MongoDB: %s", exc)

    async def push_guardrail_evaluation(
        self,
        ctx: ChatContext,
        action: str,
        violation_type: Optional[str] = None,
        score: float = 0.0,
    ) -> None:
        try:
            doc = EvaluationModel(
                request=RequestLayer(
                    user_query=ctx.user_query,
                    session_id=ctx.session_id,
                    student_id=ctx.student_id,
                    context_data={
                        "persona": ctx.collection.persona,
                        "summary": ctx.collection.summary,
                        "guardrail_action": action,
                        "violation_type": violation_type,
                    },
                ),
                retrieval=RetrievalLayer(
                    final_context="",
                    raw_documents=[],
                    config={"interception": "guardrail", "action": action},
                ),
                generation=GenerationLayer(
                    final_answer=ctx.guardrail_response or "",
                ),
                performance=PerformanceLayer(
                    latency_ms=15.0,
                    token_usage={
                        "guardrail": {
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                            "metadata": {
                                "action": action,
                                "violation_type": violation_type or "none",
                                "score": score,
                            },
                        }
                    },
                    cost=0.0,
                ),
                evaluation=EvaluationMetricsLayer(
                    is_evaluated=True,
                    judge_info={"framework": "guardrail_pipeline"},
                    metrics={"blocked": 1.0, "violation_score": score},
                ),
            )
            await self.evaluation_repo.add_eval_session(doc)
            logger.info("Guardrail interception evaluation logged to MongoDB (action=%s).", action)
        except Exception as exc:
            logger.warning("Failed to push guardrail evaluation to MongoDB: %s", exc)

    async def update_persona_and_summary_background(
        self,
        student_id: str,
        session_id: str,
        user_query: str,
        batch_history_str: str,
        current_persona: str,
        current_summary: str,
        run_persona: bool,
        run_summary: bool,
    ) -> None:
        try:
            logger.info(
                "Starting background update for persona/summary (dynamic mode). run_persona=%s, run_summary=%s",
                run_persona,
                run_summary,
            )

            tasks = []
            if run_summary:
                tasks.append(
                    self.summary_chain.ainvoke(
                        {
                            "old_summary": current_summary,
                            "new_messages": batch_history_str,
                        },
                        config={"run_name": "Update Session Summary Chain"},
                    )
                )
            else:
                tasks.append(asyncio.sleep(0))

            if run_persona:
                tasks.append(
                    self.persona_chain.ainvoke(
                        {
                            "user_persona": current_persona,
                            "messages_history": batch_history_str,
                            "user_query": user_query,
                        },
                        config={"run_name": "Update Student Persona Chain"},
                    )
                )
            else:
                tasks.append(asyncio.sleep(0))

            new_summary, persona_decision = await asyncio.gather(*tasks)

            collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
            if collection:
                if run_summary and new_summary:
                    collection.summary = new_summary
                    collection.unsummarized_count = 0
                if (
                    run_persona
                    and persona_decision
                    and getattr(persona_decision, "should_update", False)
                    and getattr(persona_decision, "updated_persona", None)
                ):
                    collection.persona = persona_decision.updated_persona
                await self.redis_provider.save_collection(collection, session_id=session_id)
                logger.info("Background update for persona/summary completed successfully.")
        except Exception as exc:
            logger.error("Failed background update for persona and summary: %s", exc, exc_info=True)

    def trigger_background_updates(self, ctx: ChatContext, graph_result: Dict[str, Any]) -> None:
        needs_persona_update = graph_result.get("needs_persona_update", False)
        needs_summary_update = graph_result.get("needs_summary_update", False)

        collection = ctx.collection
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

            asyncio.create_task(
                self.update_persona_and_summary_background(
                    student_id=ctx.student_id,
                    session_id=ctx.session_id,
                    user_query=ctx.user_query,
                    batch_history_str=batch_history_str,
                    current_persona=collection.persona,
                    current_summary=collection.summary,
                    run_persona=needs_persona_update,
                    run_summary=should_run_summary_now,
                )
            )

    async def process(
        self,
        ctx: ChatContext,
        ai_reply: str,
        graph_result: Dict[str, Any],
        latency_ms: float,
    ) -> None:
        run_step_outputs = graph_result.get("run_step_outputs") or []

        await self.save_session_turn(
            collection=ctx.collection,
            session_id=ctx.session_id,
            user_query=ctx.user_query,
            ai_reply=ai_reply,
            run_step_outputs=run_step_outputs,
        )

        asyncio.create_task(
            self.push_evaluation(
                user_query=ctx.user_query,
                context=graph_result.get("retrieved_context") or "",
                answer=ai_reply,
                student_id=ctx.student_id,
                session_id=ctx.session_id,
                run_step_outputs=run_step_outputs,
                persona=ctx.collection.persona,
                summary=ctx.collection.summary,
                llm_usage_breakdown=graph_result.get("llm_usage_breakdown") or {},
                latency_ms=latency_ms,
            )
        )

        self.trigger_background_updates(ctx, graph_result)
