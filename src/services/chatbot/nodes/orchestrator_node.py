import json
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from ..states import ChatbotState
from helpers.logger import get_chatbot_logger
from ..utils import format_messages_history

logger = get_chatbot_logger(__name__)

class RouteDecision(BaseModel):
    needs_retrieval: bool = Field(..., description="True if the query requires fetching new details from the database about academic subjects, courses, lectures, documents, or history. False for greetings, chit-chat, follow-up questions on already discussed/retrieved topics, or questions fully answered by the enrolled courses list.")
    standalone_query: str = Field(..., description="Context-resolved version of the query with pronouns replaced by actual subjects.")
    needs_persona_update: bool = Field(..., description="True if the user shares learning preferences, background, or goals.")
    needs_summary_update: bool = Field(..., description="True if a new topic is introduced or a milestone is reached.")

class OrchestratorNode:
    STATIC_SYSTEM_PROMPT = """
You are a Router and Query Rewriter for an educational chatbot system.
Analyze the query, session summary, and conversation history.

Guidelines:
1. Set needs_retrieval=False if the query only lists, counts, or checks enrolled courses (already available downstream).
2. Resolve pronouns in the standalone_query.
3. Set needs_retrieval=False if the query is a follow-up question (e.g. asking for clarification, explanation, translation, or more examples) about a topic/concept that has already been discussed in the conversation history.
"""

    DYNAMIC_CONTEXT_TEMPLATE = """
Session Summary: {session_summary}

Recent Conversation History:
{messages_history}

Current User Query: {user_query}
"""

    def __init__(self, llm: ChatOpenAI):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.STATIC_SYSTEM_PROMPT),
            ("human", self.DYNAMIC_CONTEXT_TEMPLATE),
        ])
        self.chain = self.prompt | llm.with_structured_output(RouteDecision, method="function_calling")

    async def __call__(self, state: ChatbotState) -> Dict[str, Any]:
        logger.info("OrchestratorNode invoked. Query: %s", state.user_query)

        messages_history_formatted = format_messages_history(state.messages_history)
        session_summary_str = state.session_summary or "No session summary."

        decision: RouteDecision = await self.chain.ainvoke({
            "session_summary": session_summary_str,
            "messages_history": messages_history_formatted,
            "user_query": state.user_query
        })

        logger.info("Orchestrator decision: needs_retrieval=%s, persona_update=%s, summary_update=%s, query='%s'", 
                    decision.needs_retrieval, decision.needs_persona_update, decision.needs_summary_update, decision.standalone_query)

        rag_status = "route_to_rag" if decision.needs_retrieval else "direct_answer"

        return {
            "rag_status": rag_status,
            "standalone_query": decision.standalone_query,
            "needs_persona_update": decision.needs_persona_update,
            "needs_summary_update": decision.needs_summary_update
        }
