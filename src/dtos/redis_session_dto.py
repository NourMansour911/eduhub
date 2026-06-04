from typing import Any, Dict, List

from pydantic import BaseModel, Field



class RedisSessionDTO(BaseModel):
    user_id: str = Field(..., description="User identifier for the Redis collection")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Stored chat messages")
    contexts: List[Dict[str, Any]] = Field(default_factory=list, description="Additional context for the session")
    persona: str | None = Field(default=None, description="The student's persona to inject into the chatbot context")
