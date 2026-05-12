from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Dict
from datetime import datetime

from azure.ai.documentintelligence.models import AnalyzeResult


class LectureModel(BaseModel):
    iid: Optional[str] = Field(None, alias="_id")
    lecture_id: str = Field(..., description="Unique identifier for the lecture")
    lecture_name: str = Field(..., description="Display name/title of the lecture")
    subject_id: str = Field(..., description="The subject/material id this lecture belongs to")
    subject_name: str = Field(..., description="The subject/material name this lecture belongs to")
    content: str = Field(..., description="Raw (Markdown) content of the lecture, can be used for re-processing or summarization")
    order: Optional[int] = Field(None, description="Optional lecture order within the subject")
    summaries: Dict[str, str] = Field(default_factory=dict, description="Cached summaries by level ('0', '1', '2')")
    created_at: datetime = Field(default_factory=datetime.now)


    @field_validator("iid", mode="before")
    @classmethod
    def parse_iid(cls, value: Any) -> Any:
        if value is None:
            return value
        return str(value)

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }
