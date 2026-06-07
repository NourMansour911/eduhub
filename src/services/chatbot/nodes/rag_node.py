from typing import Any, Dict
from ..states import ChatbotState
from services.chatbot.agents.rag.states import RAGSubgraphOutput
from helpers import get_logger
from langchain_core.runnables import Runnable

logger = get_logger(__name__)


class RAGNode:
    def __init__(self, rag_subgraph: Runnable):
        self.rag_subgraph: Runnable = rag_subgraph

    async def __call__(self, state: ChatbotState) -> Dict[str, Any]:
        
        serialized_prev = []
        for turn_list in state.previous_steps_outputs:
            turn_serialized = []
            for out in turn_list:
                if hasattr(out, "model_dump"):
                    turn_serialized.append(out.model_dump())
                elif isinstance(out, dict):
                    turn_serialized.append(out)
            serialized_prev.append(turn_serialized)

        logger.debug("RAGNode invoking subgraph with %d previous turns.", len(serialized_prev))

        subgraph_result = await self.rag_subgraph.ainvoke({
            "user_query": state.user_query,
            "student_id": state.student_id,
            "student_courses": state.student_courses,
            "messages_history": state.messages_history,
            "previous_steps_outputs": serialized_prev,
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
        }
