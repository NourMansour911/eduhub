from datetime import datetime, timezone

from pydantic import BaseModel, Field


class SessionArchiveMetadataDTO(BaseModel):
    chunk_id: str = Field(..., description="Unique identifier for the archived session record")
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    archived_at: datetime = Field(default_factory=datetime.now, description="Archival timestamp in UTC")