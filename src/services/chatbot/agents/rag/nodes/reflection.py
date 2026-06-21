from typing import Dict, Any, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from ..states import RAGSubgraphState, ReflectionDecision
from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


from services.chatbot.utils import format_step_output, log_duration


class ReflectionNode:
    STATIC_SYSTEM_PROMPT = """
You are a Reflection node in a RAG system.
Look at the retrieved context (Step Outputs) and determine if it contains enough information to answer the user's query.

Rules:
1. Do NOT scrutinize the semantic meaning/correctness of the returned data. Only check if the requested type of output (e.g. summaries, course details) was successfully returned.
2. Return 'success' even if the data seems incorrect, unrelated, or like dummy test data.

Output Schema:
{format_instructions}
"""

    DYNAMIC_CONTEXT_TEMPLATE = """
User Query:
{user_query}

Step Outputs (Retrieved Context):
{step_outputs}
"""

    def __init__(self, llm: ChatOpenAI):
        self.parser = PydanticOutputParser(pydantic_object=ReflectionDecision)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.STATIC_SYSTEM_PROMPT),
            ("human", self.DYNAMIC_CONTEXT_TEMPLATE),
        ]).partial(
            format_instructions=self.parser.get_format_instructions()
        )
        self.chain = self.prompt | llm | self.parser

    async def __call__(self, state: RAGSubgraphState) -> Dict[str, Any]:
        user_query = state.user_query
        step_outputs = state.step_outputs
        
        step_outputs_formatted = "\n\n".join([format_step_output(out) for out in step_outputs]) if step_outputs else "No step outputs."

        logger.info(
            "\n" + "="*80 + "\n"
            "[REFLECTION NODE] EVALUATING RETRIEVED CONTEXT\n"
            f"Session ID: {state.session_id}\n"
            f"User Query: {user_query}\n"
            f"Step Outputs:\n{step_outputs_formatted}\n"
            + "="*80
        )

        async with log_duration(logger, "Reflection Node Chain Call", session_id=state.session_id):
            decision: ReflectionDecision = await self.chain.ainvoke({
                "user_query": user_query,
                "step_outputs": step_outputs_formatted,
                "format_instructions": self.parser.get_format_instructions()
            })

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
            result["replan_count"] = state.replan_count + 1

        return result
