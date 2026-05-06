from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class LectureCreateRequest(BaseModel):
    url: str = Field(..., description="url of the lecture content to be processed ")
    lecture_id: str = Field(..., description="Unique identifier for the lecture.")
    lecture_name: str = Field(..., description="Display name/title of the lecture.")
    subject_id: str = Field(..., description="The subject/material id this lecture belongs to.")
    subject_name: str = Field(..., description="The subject/material name this lecture belongs to.")
    order: Optional[int] = Field(None, description="Optional lecture order within the subject.")


class LectureResponse(BaseModel):
    status: str = Field("success", description="Response status")
    lecture_id: str = Field(..., description="Unique identifier for the lecture.")



class DeleteLectureResponse(BaseModel):
    status: str = Field("success", description="Response status")
    lecture_id: Optional[str] = Field(None, description="Lecture identifier used for deletion.")
    subject_id: Optional[str] = Field(None, description="Subject identifier used for deletion.")
    deleted_count: int = Field(..., description="Number of deleted documents.")


class LectureListResponse(BaseModel):
    items: list[LectureResponse] = Field(..., description="List of lectures.")


class LectureDeleteRequest(BaseModel):
    lecture_id: Optional[str] = Field(None, description="Delete a single lecture by lecture_id.")
    subject_id: Optional[str] = Field(None, description="Delete all lectures for a subject_id.")

    @model_validator(mode="after")
    def validate_target(self):
        if not self.lecture_id and not self.subject_id:
            raise ValueError("Either lecture_id or subject_id must be provided.")
        if self.lecture_id and self.subject_id:
            raise ValueError("Provide only one of lecture_id or subject_id.")
        return self
