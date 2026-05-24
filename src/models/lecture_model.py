from pydantic import Field
from typing import Optional, Dict
from datetime import datetime, timezone

from azure.ai.documentintelligence.models import AnalyzeResult

from models.mongo_document_model import MongoDocumentModel


class LectureModel(MongoDocumentModel):
    lecture_id: str = Field(..., description="Unique identifier for the lecture")
    lecture_name: str = Field(..., description="Display name/title of the lecture")
    subject_id: str = Field(..., description="The subject/material id this lecture belongs to")
    subject_name: str = Field(..., description="The subject/material name this lecture belongs to")
    content: str = Field(..., description="Raw (Markdown) content of the lecture, can be used for re-processing or summarization")
    order: Optional[int] = Field(None, description="Optional lecture order within the subject")
    summaries: Dict[str, str] = Field(default_factory=dict, description="Cached summaries by level ('0', '1', '2')")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
