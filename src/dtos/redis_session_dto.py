from typing import Any, Dict, List

from pydantic import BaseModel, Field

from services.chatbot.agents.rag.states import StepOutput


class RedisSessionDTO(BaseModel):
    user_id: str = Field(..., description="User identifier for the Redis collection")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Stored chat messages")
    contexts: List[List[StepOutput]] = Field(default_factory=list, description="Step outputs history list of list")
    persona: str | None = Field(default=None, description="The student's persona to inject into the chatbot context")
    summary: str | None = Field(default=None, description="Session summary cached in Redis")
    student_courses: str | None = Field(default=None, description="Cached student courses formatted string")
