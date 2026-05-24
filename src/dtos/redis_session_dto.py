from typing import Any, Dict, List

from pydantic import BaseModel, Field


class RedisSessionDTO(BaseModel):
    user_id: str = Field(..., description="User identifier for the Redis collection")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="Stored chat messages")
