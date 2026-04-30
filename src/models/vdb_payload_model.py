from typing import Any, Dict

from pydantic import BaseModel, Field


class VDBChunkPayload(BaseModel):
    text: str = Field(..., description="Chunk text content")
    metadata: dict = Field(default_factory=dict, description="Metadata associated with the chunk")
