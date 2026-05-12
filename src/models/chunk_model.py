
from pydantic import BaseModel, Field
from typing import Optional

class ChunkMetadata(BaseModel):
    chunk_id: str = Field(..., description="Unique identifier for the chunk")
    lecture_id: str = Field(..., description="ID of the lecture this chunk belongs to")
    lecture_name: str = Field(..., description="Title of the lecture")
    subject_id: str = Field(..., description="ID of the subject")
    subject_name: str = Field(..., description="Name of the subject")
    chunk_index: int = Field(..., description="Index of the chunk within the lecture")
    lecture_order: Optional[int] = Field(None, description="Lecture order within subject")
