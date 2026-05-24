
from pydantic import Field
from datetime import datetime, timezone

from models.mongo_document_model import MongoDocumentModel


class AnswerModel(MongoDocumentModel):
    question: str = Field(..., description="The question text")
    text: str = Field(..., description="Text of the answer")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
