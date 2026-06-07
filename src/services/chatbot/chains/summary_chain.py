from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

SYSTEM_TMPL = """
You are an educational session summary updater.
Your task is to take an existing session summary and update it to incorporate the latest user-AI interactions.
Keep the summary concise, coherent, and formal. Preserve all key educational goals, intent, and technical terms. Do not output titles or extra labels.

Existing Session Summary:
{old_summary}
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TMPL),
        (
            "human",
            """
Latest Interactions:
{new_messages}

Generate the updated, merged session summary incorporating these latest interactions.
""",
        ),
    ]
)


def build_summary_chain(llm: ChatOpenAI) -> Runnable:
    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        old_summary = (inputs.get("old_summary") or "").strip() or "No existing summary."
        new_messages = (inputs.get("new_messages") or "").strip()
        if not new_messages:
            raise ValueError("new_messages is required")

        return {"old_summary": old_summary, "new_messages": new_messages}

    return RunnableLambda(prepare_input) | PROMPT | llm | StrOutputParser()
