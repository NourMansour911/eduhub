from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class SessionActionResponseDTO(BaseModel):
    action: str = Field(..., description="Session action name")
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    redis_collection_name: str = Field(..., description="Redis collection name for the session")
    qdrant_collection_name: Optional[str] = Field(None, description="Qdrant collection name when archived")
    qdrant_record_id: Optional[str] = Field(None, description="Qdrant record identifier when archived")
    stored_in_qdrant: bool = Field(False, description="Whether the session was archived in Qdrant")
    redis_cleared: bool = Field(False, description="Whether the Redis session was cleared")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Action timestamp in UTC")