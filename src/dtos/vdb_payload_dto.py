from typing import Any

from pydantic import BaseModel, Field


class VDBChunkPayload(BaseModel):
    text: str = Field(..., description="Chunk text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata associated with the chunk")


class VDBSearchResultPayload(BaseModel):
    id: str = Field(..., description="Chunk identifier")
    relevance_score: float | None = Field(default=None, description="Chunk relevance score if available")
    text: str = Field(default="", description="Chunk text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata associated with the chunk")
