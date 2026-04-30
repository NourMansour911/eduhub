
from pydantic import BaseModel, Field
from datetime import datetime

class AnsChunkMetadata(BaseModel):
    question_id: str = Field(..., description="File identifier")
    weight: float = Field(..., description="Weight of the chunk in grading")
    chunk_order: int = Field(..., description="Order of the chunk in the document")
    created_at: datetime = Field(default=datetime.now())
    word_count: int = Field(..., description="Word count in chunk")
