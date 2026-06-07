from typing import Callable, Awaitable
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from langchain_core.runnables import Runnable


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
            updated = await summary_chain.ainvoke({
                "old_summary": old_summary,
                "new_messages": new_interactions,
            })
            await callback(updated)
            return "Session summary updated successfully."
        except Exception as e:
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
            decision = await persona_chain.ainvoke({
                "user_persona": current_persona,
                "messages_history": messages_history,
                "user_query": user_query,
            })
            if decision.should_update and decision.updated_persona:
                await callback(decision.updated_persona)
                return "Student persona updated successfully."
            return "Persona analysis complete. No update was deemed necessary."
        except Exception as e:
            return f"Error updating student persona: {str(e)}"

    return StructuredTool.from_function(
        coroutine=update_persona,
        name="update_student_persona",
        description="Analyzes interaction history and updates the student's learning persona profile.",
    )
