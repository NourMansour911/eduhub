from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI


class PersonaUpdateDecision(BaseModel):
    should_update: bool = Field(..., description="Whether the student persona needs an update based on the latest interaction")
    updated_persona: Optional[str] = Field(None, description="The new updated persona if should_update is True, otherwise None")


SYSTEM_TMPL = """
You are Persona Analyzer. Analyze the student's current persona, the conversation history, and their latest query to decide if their learning persona (preferences, level, tone, interests) has changed or needs an update.

Current Student Persona:
{user_persona}

Conversation History (last 4 messages):
{messages_history}

Latest User Query: {user_query}

{format_instructions}
"""

PROMPT = ChatPromptTemplate.from_template(SYSTEM_TMPL)


def build_persona_chain(llm: ChatOpenAI) -> Runnable:
    parser = PydanticOutputParser(pydantic_object=PersonaUpdateDecision)
    prompt = PROMPT.partial(format_instructions=parser.get_format_instructions())

    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        user_persona = (inputs.get("user_persona") or "General friendly student.").strip()
        messages_history = (inputs.get("messages_history") or "").strip()
        user_query = (inputs.get("user_query") or "").strip()
        return {
            "user_persona": user_persona,
            "messages_history": messages_history,
            "user_query": user_query,
        }

    return RunnableLambda(prepare_input) | prompt | llm | parser
