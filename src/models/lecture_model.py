from pydantic import BaseModel, Field
from typing import Optional, Any
from bson import ObjectId
from datetime import datetime

from azure.ai.documentintelligence.models import AnalyzeResult


class LectureModel(BaseModel):
    iid: Optional[ObjectId] = Field(None, alias="_id")
    lecture_id: str = Field(..., description="Unique identifier for the lecture")
    lecture_name: str = Field(..., description="Display name/title of the lecture")
    subject_id: str = Field(..., description="The subject/material id this lecture belongs to")
    
    subject_name: str = Field(..., description="The subject/material name this lecture belongs to")
    content: AnalyzeResult = Field(..., description="Azure Document Intelligence AnalyzeResult for the lecture content")
    order: Optional[int] = Field(None, description="Optional lecture order within the subject")
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        "json_encoders": {
            ObjectId: str,
            AnalyzeResult: (lambda v: v.as_dict() if hasattr(v, "as_dict") else v),
        },
    }
