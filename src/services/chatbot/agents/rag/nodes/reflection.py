from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from ..states import RAGSubgraphState, ReflectionDecision
from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


from services.chatbot.utils import format_step_output, log_duration, format_nested_step_outputs


class ReflectionNode:
    STATIC_SYSTEM_PROMPT = """
You are a Reflection node in a RAG system.
Look at the retrieved context (Step Outputs) and determine if it contains enough information to answer the user's query.

Rules:
1. Do NOT scrutinize the semantic meaning/correctness of the returned data. Only check if the requested type of output (e.g. summaries, course details) was successfully returned.
2. Return 'success' even if the data seems incorrect, unrelated, or like dummy test data.
3. If a step failed and returns a Failure/Error with a 'Clarification Recommendation' or 'Explanation':
   - Read the details to determine if there is a benefit to replanning (e.g. searching a different course, re-attempting with a corrected query or different parameters). If so, choose 'replan' and provide a constructive suggestion in 'reason'.
   - If the error/recommendation indicates that the system fundamentally cannot resolve the user's request (e.g. database down, student not enrolled in the course, query is totally ambiguous, or no other tools can help), choose 'clarification' and output the 'Clarification Recommendation' as your 'clarification_question'.
"""

    DYNAMIC_CONTEXT_TEMPLATE = """
User Query:
{user_query}

Current Attempt Step Outputs:
{current_attempt_tool_outputs}
"""

    def __init__(self, llm: ChatOpenAI):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.STATIC_SYSTEM_PROMPT),
            ("human", self.DYNAMIC_CONTEXT_TEMPLATE),
        ])
        self.chain = self.prompt | llm.with_structured_output(ReflectionDecision, method="function_calling")

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        user_query = state.user_query
        current_attempt = state.current_attempt_tool_outputs
        
        current_attempt_formatted = "\n\n".join([format_step_output(out, for_planning=False) for out in current_attempt]) if current_attempt else "No step outputs."

        logger.info(
            "\n" + "="*80 + "\n"
            "[REFLECTION NODE] EVALUATING RETRIEVED CONTEXT\n"
            f"Session ID: {state.session_id}\n"
            f"Plan Attempt: {state.plan_attempts_count}\n"
            f"User Query: {user_query}\n"
            f"Current Attempt Step Outputs:\n{current_attempt_formatted}\n"
            + "="*80
        )

        async with log_duration(logger, f"Reflection Node Chain Call (Attempt {state.plan_attempts_count})", session_id=state.session_id):
            decision: ReflectionDecision = await self.chain.ainvoke({
                "user_query": user_query,
                "current_attempt_tool_outputs": current_attempt_formatted,
            }, config={"run_name": f"Reflection Chain Run (Attempt {state.plan_attempts_count})"})

        logger.info(
            "\n" + "-"*80 + "\n"
            "[REFLECTION NODE] DECISION RENDERED\n"
            f"Session ID: {state.session_id}\n"
            f"Decision: {decision.decision.upper()}\n"
            f"Reason: {decision.reason}\n"
            f"Clarification Question: {decision.clarification_question or 'None'}\n"
            + "-"*80
        )

        result = {
            "reflection_decision": decision
        }
        if decision.decision == "replan":
            result["plan_attempts_count"] = state.plan_attempts_count + 1

        return result
