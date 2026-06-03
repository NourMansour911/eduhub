from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class FailureInfo(BaseModel):
    message: str = Field(..., description="Technical or user-friendly error message")
    clarification_message: Optional[str] = Field(default=None, description="Predefined question to ask the user if clarification is needed")
    explanation: Optional[str] = Field(default=None, description="Detailed explanation of the failure for the LLM")


class RAGContextDTO(BaseModel):
    tool_name: str = Field(default="", description="Name of the tool to use for retrieval")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the retrieval tool")
    source: str = Field(..., description="The source of the retrieved context")
    order: Optional[int] = Field(default=None)
    content: Dict[str, Any] = Field(default_factory=dict, description="The retrieved context content (populated on success)")
    failure_info: Optional[FailureInfo] = Field(default=None, description="Details about the failure (populated on failure)")
