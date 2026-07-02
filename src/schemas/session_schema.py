from typing import Optional

from pydantic import BaseModel, Field

class SessionRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user starting the session.")
    session_id: str = Field(..., description="Unique identifier for the session being started.")

class SessionStartResponse(BaseModel):
    cache_key: str = Field(..., description="Key for the session data stored in the cache.")

class SessionEndResponse(BaseModel):
    summary: str = Field(..., description="Summary of the session content.")
    vdb_record_id: Optional[str] = Field(
        None,
        description="ID of the record stored in the vector database, if applicable.",
    )

class DeleteSessionResponse(BaseModel):
    user_id: str = Field(..., description="User ID associated with the session")
    session_id: str = Field(..., description="ID of the deleted session")
    deleted: bool = Field(..., description="Indicates if the deletion was successful")
    message: str = Field(..., description="Status message")


class DeleteUserSessionsResponse(BaseModel):
    user_id: str = Field(..., description="User ID associated with the deleted sessions")
    deleted: bool = Field(..., description="Indicates if the deletion was successful")
    message: str = Field(..., description="Status message")


