from typing import Any, List, Optional
from pydantic import BaseModel, Field
from services.chatbot.agents.rag.states import StepOutput


class ChatbotState(BaseModel):
    user_query: str
    student_id: str
    session_id: str
    student_courses: str = ""
    messages_history: List[Any] = Field(default_factory=list)
    user_persona: Optional[str] = None
    session_summary: Optional[str] = None
    should_update_persona: bool = False
    should_update_summary: bool = False
    previous_steps_outputs: List[List[StepOutput]] = Field(default_factory=list)
    
    # RAG results passed to Answering Node and saved to Redis
    retrieved_context: Optional[str] = None
    run_step_outputs: List[StepOutput] = Field(default_factory=list)
    
    # RAG execution status indicators
    rag_status: Optional[str] = None
    rag_clarification_question: Optional[str] = None
    rag_error_message: Optional[str] = None
    
    # Final generated answer
    response: Optional[str] = None
