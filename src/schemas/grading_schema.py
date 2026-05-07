from typing import Optional, List

from pydantic import BaseModel, Field




class RefGradingRequest(BaseModel):
    question_text: str = Field(..., description="The question text.")
    answer: str = Field(..., description="The reference answer provided by the doctor.")

class RefGradingResponse(BaseModel):
    question_id: str = Field(..., description="Stored answer identifier.")

class GradingRequest(BaseModel):
    question_id: str = Field(..., description="Stored answer identifier.")
    answer: str = Field(..., description="The student's answer to be graded.")


class GradingResponse(BaseModel):
    score: float = Field(..., ge=0, le=1, description="Final weighted score.")
    feedback: Optional[str] = Field(None, description="Optional feedback for the student.")
    student_answer: Optional[str] = Field(None, description="The student's answer that was graded.")
    question_id: Optional[str] = Field(None, description="The question identifier.")
    reference_answer: Optional[str] = Field(None, description="The reference answer used for grading.")


class BatchGradingRequest(BaseModel):
    items: List[GradingRequest] = Field(..., description="List of answers to grade.")
    threshold: float = Field(0.3, ge=0, le=1, description="Scores below this value are rounded down to zero.")


class BatchGradingResponse(BaseModel):
    results: List[GradingResponse] = Field(..., description="List of grading results.")


