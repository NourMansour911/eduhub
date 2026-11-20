import asyncio
import json
from typing import Any, Dict, List, Optional
from langchain_core.runnables import Runnable

from dtos.redis_session_dto import RedisSessionDTO
from helpers.logger import get_chatbot_logger
from integrations.redis_provider import RedisProvider
from models import EvaluationModel
from models.evaluation_model import GenerationLayer, PerformanceLayer, RequestLayer, RetrievalLayer
from repositories.evaluation_repo import EvaluationRepo
from services.chatbot.utils import clip_message_content
from .preflight import ChatContext

logger = get_chatbot_logger(__name__)


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
                ),
                performance=PerformanceLayer(
                    latency_ms=latency_ms,
                    token_usage=llm_usage_breakdown or {},
                ),
            )
            await self.evaluation_repo.add_eval_session(doc)
            logger.info("Evaluation session pushed to MongoDB.")
        except Exception as exc:
            logger.warning("Failed to push evaluation session to MongoDB: %s", exc)

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
