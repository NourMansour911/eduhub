from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI


SYSTEM_TMPL = """
You are an educational institution chatbot assistant that turns a chat session into a compact archival summary.

Rules:
- Use only the provided messages
- Preserve the main goal, decisions, learner intent, and important details
- Do not invent missing information
- Keep the summary coherent and naturally written
- Keep educational and technical terms exactly as written
- Do not output titles or extra labels
- Keep the tone suitable for a formal educational environment
"""


PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TMPL),
        (
            "human",
            """
Messages:
{messages}

Write a single archival summary for this session.
""",
        ),
    ]
)


def build_session_summary_chain(llm: ChatOpenAI) -> Runnable:
    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        messages = (inputs.get("messages") or "").strip()
        if not messages:
            raise ValueError("messages is required")

        return {"messages": messages}

    return RunnableLambda(prepare_input) | PROMPT | llm | StrOutputParser()