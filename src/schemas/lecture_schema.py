from typing import Any, Optional

from pydantic import BaseModel, Field


class LectureCreateRequest(BaseModel):
    lecture_id: str = Field(..., description="Unique identifier for the lecture.")
    subject_id: str = Field(..., description="The subject/material id this lecture belongs to.")
    subject_name: str = Field(..., description="The subject/material name this lecture belongs to.")
    content: Any = Field(..., description="AnalyzeResult content serialized as JSON.")
    order: Optional[int] = Field(None, description="Optional lecture order within the subject.")


class LectureResponse(BaseModel):
    iid: Optional[str] = Field(None, alias="_id", description="Stored lecture identifier.")
    lecture_id: str = Field(..., description="Unique identifier for the lecture.")
    subject_id: str = Field(..., description="The subject/material id this lecture belongs to.")
    subject_name: str = Field(..., description="The subject/material name this lecture belongs to.")
    content: Any = Field(..., description="AnalyzeResult content serialized as JSON.")
    order: Optional[int] = Field(None, description="Optional lecture order within the subject.")


class DeleteLectureResponse(BaseModel):
    lecture_id: Optional[str] = Field(None, description="Lecture identifier used for deletion.")
    subject_id: Optional[str] = Field(None, description="Subject identifier used for deletion.")
    deleted_count: int = Field(..., description="Number of deleted documents.")


class LectureListResponse(BaseModel):
    items: list[LectureResponse] = Field(..., description="List of lectures.")
