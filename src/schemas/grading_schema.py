from typing import Optional

from pydantic import BaseModel, Field




class RefGradingRequest(BaseModel):
    answer: str = Field(..., description="The reference answer provided by the doctor.")

class RefGradingResponse(BaseModel):
    question_id: str = Field(..., description="Stored answer identifier.")

class GradingRequest(BaseModel):
    question_id: str = Field(..., description="Stored answer identifier.")
    answer: str = Field(..., description="The student's answer to be graded.")


class GradingResponse(BaseModel):
    score: float = Field(..., ge=0, le=1, description="Final weighted score.")
    feedback: Optional[str] = Field(None, description="Optional feedback for the student.")
    reference_answer: Optional[str] = Field(None, description="The reference answer used for grading.")
    student_answer: Optional[str] = Field(None, description="The student's answer that was graded.")


    

