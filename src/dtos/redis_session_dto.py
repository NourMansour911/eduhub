from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RedisSessionDTO(BaseModel):
    user_id: str = Field(..., description="User identifier for the Redis collection")
    plan: str = Field(default="free", description="Student plan tier: free, standard, premium")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Stored chat messages")
    contexts: List[List[Any]] = Field(default_factory=list, description="Step outputs history list of list")
    persona: Optional[str] = Field(default=None, description="The student's persona to inject into the chatbot context")
    summary: Optional[str] = Field(default=None, description="Session summary cached in Redis")
    student_courses: Optional[str] = Field(default=None, description="Cached student courses formatted string")
    unsummarized_count: int = Field(default=0, description="Number of new messages since last session summary update")

