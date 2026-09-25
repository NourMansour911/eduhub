from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI


class PersonaUpdateDecision(BaseModel):
    should_update: bool = Field(..., description="Whether the student persona needs an update based on the latest interaction")
    updated_persona: Optional[str] = Field(None, description="The new updated persona if should_update is True, otherwise None")


SYSTEM_MSG = """
You are Persona Analyzer. Analyze the student's current persona, the conversation history, and their latest query to decide if their learning persona (preferences, level, tone, interests) has changed or needs an update.
Note: Messages in the conversation history may be clipped/truncated for brevity (marked with '[clipped for brevity]').
"""

CONTEXT_MSG = """
Current Student Persona:

{user_persona}

Conversation History (last 4 messages):
{messages_history}

Latest User Query: {user_query}
"""

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_MSG),
    ("human", CONTEXT_MSG),
])


def build_persona_chain(llm: ChatOpenAI, prompt: Optional[ChatPromptTemplate] = None) -> Runnable:
    structured_llm = llm.with_structured_output(PersonaUpdateDecision, method="function_calling")
    prompt_to_use = prompt or PROMPT

    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        user_persona = (inputs.get("user_persona") or "General friendly student.").strip()
        messages_history = (inputs.get("messages_history") or "").strip()
        user_query = (inputs.get("user_query") or "").strip()
        return {
            "user_persona": user_persona,
            "messages_history": messages_history,
            "user_query": user_query,
        }

    return RunnableLambda(prepare_input) | prompt_to_use | structured_llm
