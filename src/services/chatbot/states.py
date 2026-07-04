from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from services.chatbot.agents.rag.states import StepOutput


class ChatbotState(BaseModel):
    user_query: str
    student_id: str
    session_id: str
    student_courses: str = ""
    user_persona: Optional[str] = None
    session_summary: Optional[str] = None
    standalone_query: Optional[str] = None
    needs_persona_update: bool = False
    needs_summary_update: bool = False
    messages_history: List[Any] = Field(default_factory=list)
    past_messages_tool_outputs: List[StepOutput] = Field(default_factory=list)
    retrieved_context: Optional[str] = None
    run_step_outputs: List[StepOutput] = Field(default_factory=list)
    rag_status: Optional[str] = None
    rag_clarification_question: Optional[str] = None
    rag_error_message: Optional[str] = None
    response: Optional[str] = None
    llm_usage: Optional[Dict[str, Any]] = None
    llm_metadata: Optional[Dict[str, Any]] = None
