from typing import Any, Dict, Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI

from helpers import get_logger
from ..states import ChatbotState

logger = get_logger(__name__)


class RouteDecision(BaseModel):
    decision: Literal["retrieve", "direct"] = Field(
        ...,
        description="Choose 'retrieve' if answering the user query requires fetching external facts/details (like searching in lectures, course details, summaries, regulations). Choose 'direct' if it can be answered directly using only the chat history, session summary, or student persona."
    )


class OrchestratorNode:
    ROUTE_PROMPT = """
You are Luma's Orchestrator Router.
Analyze the user's latest query to determine if answering it requires retrieving external facts/details (like searching in lectures, course details, summaries, regulations) or if you can answer it directly.

User Query:
{user_query}

{format_instructions}
"""

    def __init__(self, llm: ChatOpenAI):
        # Route Chain
        self.route_parser = PydanticOutputParser(pydantic_object=RouteDecision)
        self.route_prompt = ChatPromptTemplate.from_template(self.ROUTE_PROMPT).partial(
            format_instructions=self.route_parser.get_format_instructions()
        )
        self.route_chain = self.route_prompt | llm | self.route_parser

    async def __call__(self, state: ChatbotState) -> Dict[str, Any]:
        logger.debug("Orchestrator routing query: %s", state.user_query)

        decision: RouteDecision = await self.route_chain.ainvoke({
            "user_query": state.user_query,
        })

        logger.debug("Orchestrator route decision result: %s", decision.decision)

        return {
            "rag_status": "retrieve" if decision.decision == "retrieve" else "direct",
        }
