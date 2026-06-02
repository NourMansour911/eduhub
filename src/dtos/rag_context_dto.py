from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RAGContextDTO(BaseModel):
    status: Literal[0, 1] = Field(..., description="Status of the retrieved context")
    tool_name: str = Field(default="", description="Name of the tool to use for retrieval")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the retrieval tool")
    source: str = Field(..., description="The source of the retrieved context")
    order: Optional[int] = Field(default=None)
    content: Dict[str, Any] = Field(default_factory=dict, description="The retrieved context content")