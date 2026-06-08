from typing import Callable, Awaitable
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_core.runnables import Runnable
from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


class UpdateSummaryInput(BaseModel):
    new_interactions: str = Field(
        ...,
        description="The latest student-tutor exchange to incorporate into the session summary.",
    )


def create_update_summary_tool(
    summary_chain: Runnable,
    old_summary: str,
    callback: Callable[[str], Awaitable[None]],
) -> StructuredTool:
    async def update_summary(new_interactions: str) -> str:
        """Updates the running session summary to incorporate the latest user-AI interactions."""
        try:
            logger.info("Summary update tool called with new interactions:\n%s", new_interactions)
            updated = await summary_chain.ainvoke({
                "old_summary": old_summary,
                "new_messages": new_interactions,
            })
            logger.info("Summary updated.\nOld Summary: %s\nNew Summary: %s", old_summary, updated)
            await callback(updated)
            return "Session summary updated successfully."
        except Exception as e:
            logger.error("Error updating session summary: %s", str(e), exc_info=True)
            return f"Error updating session summary: {str(e)}"

    return StructuredTool.from_function(
        coroutine=update_summary,
        name="update_session_summary",
        description="Updates the running session summary with the latest student-tutor interaction details.",
        args_schema=UpdateSummaryInput,
    )


def create_update_persona_tool(
    persona_chain: Runnable,
    current_persona: str,
    messages_history: str,
    user_query: str,
    callback: Callable[[str], Awaitable[None]],
) -> StructuredTool:
    async def update_persona() -> str:
        """Analyzes the current interaction and updates the student persona profile if needed."""
        try:
            logger.info("Persona analyzer tool called.\nUser Query: %s\nCurrent Persona: %s", user_query, current_persona)
            decision = await persona_chain.ainvoke({
                "user_persona": current_persona,
                "messages_history": messages_history,
                "user_query": user_query,
            })
            logger.info(
                "Persona update decision result:\nShould Update: %s\nUpdated Persona: %s",
                decision.should_update,
                decision.updated_persona,
            )
            if decision.should_update and decision.updated_persona:
                await callback(decision.updated_persona)
                return "Student persona updated successfully."
            return "Persona analysis complete. No update was deemed necessary."
        except Exception as e:
            logger.error("Error updating student persona: %s", str(e), exc_info=True)
            return f"Error updating student persona: {str(e)}"

    return StructuredTool.from_function(
        coroutine=update_persona,
        name="update_student_persona",
        description="Analyzes interaction history and updates the student's learning persona profile.",
    )

