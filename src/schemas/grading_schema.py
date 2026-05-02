from typing import Optional

from pydantic import BaseModel, Field




class RefGradingRequest(BaseModel):
    answer: str = Field(..., description="The reference answer provided by the doctor.")

class RefGradingResponse(BaseModel):
    question_id: str = Field(..., description="Question identifier.")

class GradingRequest(BaseModel):
    question_id: str = Field(..., description="Question identifier.")
    boost_factor: Optional[float] = Field(default=1.0, description="Factor to boost the grading score.")
    answer: str = Field(..., description="The student's answer to be graded.")
    
    
class GradingDetailItem(BaseModel):
    teacher_chunk: str = Field(..., description="Reference chunk text.")
    best_student_chunk: str = Field(..., description="Best matching student chunk text.")
    similarity: float = Field(..., ge=0, le=1, description="Best semantic similarity value.")
    score: float = Field(..., ge=0, le=1, description="Final score for this teacher chunk.")


class GradingResponse(BaseModel):
    final_score: float = Field(..., ge=0, le=1, description="Final weighted score.")
    details: list[GradingDetailItem] = Field(default_factory=list)

class AnswerChunkItem(BaseModel):
    text: str = Field(..., description="Chunk text content.")
    weight: float = Field(
        ...,
        ge=0,
        le=1,
        description="Chunk weight.",
    )


class AnswerChunkingResponse(BaseModel):
    question_id: str = Field(..., description="Question identifier.")
    chunks: list[AnswerChunkItem] = Field(
        ...,
        description="Reference answer chunks.",
    )
    
    
    

