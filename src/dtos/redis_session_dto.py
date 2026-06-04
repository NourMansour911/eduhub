from typing import Any, Dict, List

from pydantic import BaseModel, Field

from src.services.chatbot.agents.rag.states import StepOutput


class RedisSessionDTO(BaseModel):
    user_id: str = Field(..., description="User identifier for the Redis collection")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Stored chat messages")
    contexts: List[StepOutput] = Field(default_factory=list, description="Additional context for the session")
