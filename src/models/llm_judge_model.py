from datetime import datetime, timezone

from pydantic import Field

from models.mongo_document_model import MongoDocumentModel


class LLMJudgeInputModel(MongoDocumentModel):
    user_query: str = Field(..., description="The user's original query")
    context: str = Field(..., description="Context sent to the answer generator")
    answer: str = Field(..., description="The answer that will be judged by the LLM")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))