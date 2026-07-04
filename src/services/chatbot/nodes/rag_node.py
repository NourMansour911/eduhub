from typing import Any, Dict
from ..states import ChatbotState
from services.chatbot.agents.rag.states import RAGSubgraphOutput
from helpers.logger import get_chatbot_logger
from langchain_core.runnables import Runnable

logger = get_chatbot_logger(__name__)


class RAGNode:
    def __init__(self, rag_subgraph: Runnable):
        self.rag_subgraph: Runnable = rag_subgraph

    async def __call__(self, state: ChatbotState) -> Dict[str, Any]:
        logger.info("RAGNode invoking subgraph.")

        subgraph_result = await self.rag_subgraph.ainvoke({
            "user_query": state.standalone_query or state.user_query,
            "student_id": state.student_id,
            "session_id": state.session_id,
            "student_courses": state.student_courses,
            "messages_history": state.messages_history,
        })

        retriving_results: RAGSubgraphOutput = subgraph_result.get("retriving_results")
        if not retriving_results:
            return {
                "rag_status": "failed",
                "rag_error_message": "No retrieval results returned from subgraph"
            }

        return {
            "retrieved_context": retriving_results.retrieved_context,
            "run_step_outputs": retriving_results.run_step_outputs,
            "rag_status": retriving_results.status,
            "rag_clarification_question": retriving_results.clarification_question,
            "rag_error_message": retriving_results.error_message,
            "llm_usage_breakdown": {"rag": retriving_results.rag_llm_usage},
        }
