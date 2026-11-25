from typing import Optional

from pydantic import BaseModel, Field, field_validator

from helpers.utils import CleanMarkdownStr

class SessionRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user starting the session.")
    session_id: str = Field(..., description="Unique identifier for the session being started.")
    plan: str = Field(default="free", description="Subscription plan tier: free, standard, premium")

    @field_validator("plan", mode="before")
    @classmethod
    def validate_and_default_plan(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "free"
        normalized = str(v).lower().strip()
        from core.plans import PLANS
        if normalized not in PLANS:
            raise ValueError(f"Invalid plan '{v}'. Allowed plans are: {list(PLANS.keys())}")
        return normalized

class SessionStartResponse(BaseModel):
    cache_key: str = Field(..., description="Key for the session data stored in the cache.")

class UpdateUserPlanRequest(BaseModel):
    plan: str = Field(default="free", description="New target plan tier: free, standard, premium")

    @field_validator("plan", mode="before")
    @classmethod
    def validate_and_default_plan(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "free"
        normalized = str(v).lower().strip()
        from core.plans import PLANS
        if normalized not in PLANS:
            raise ValueError(f"Invalid plan '{v}'. Allowed plans are: {list(PLANS.keys())}")
        return normalized

class UpdateUserPlanResponse(BaseModel):
    user_id: str = Field(..., description="User ID whose plan was updated")
    plan: str = Field(..., description="Active plan name after update")
    litellm_synced: bool = Field(..., description="Whether LiteLLM database was updated")
    active_sessions_updated: int = Field(..., description="Number of currently active sessions updated in Redis")
    message: str = Field(..., description="Status message")

class SessionEndResponse(BaseModel):
    summary: CleanMarkdownStr = Field(..., description="Summary of the session content.")
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


