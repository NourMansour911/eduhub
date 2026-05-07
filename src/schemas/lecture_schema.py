from typing import Any, Optional

from pydantic import BaseModel, Field


class LectureStoreRequest(BaseModel):
    url: str = Field(..., description="url of the lecture content to be processed ")
    lecture_id: str = Field(..., description="Unique identifier for the lecture.")
    lecture_name: str = Field(..., description="Display name/title of the lecture.")
    subject_id: str = Field(..., description="The subject/material id this lecture belongs to.")
    subject_name: str = Field(..., description="The subject/material name this lecture belongs to.")
    order: Optional[int] = Field(None, description="Optional lecture order within the subject.")


class LectureResponse(BaseModel):
    status: str = Field("success", description="Response status")
    lecture_id: str = Field(..., description="Unique identifier for the lecture.")


class LectureListResponse(BaseModel):
    items: list[LectureResponse] = Field(..., description="List of lectures.")


class DeleteLectureResponse(BaseModel):
    status: str = Field("success", description="Response status")
    deleted_count: int = Field(..., description="Number of deleted documents.")


class LectureDeleteByIdRequest(BaseModel):
    lecture_id: str = Field(..., description="Delete a single lecture by lecture_id.")


class LectureDeleteBySubjectRequest(BaseModel):
    subject_id: str = Field(..., description="Delete all lectures for a subject_id.")
