from typing import Optional

from pydantic import BaseModel, Field




class RefGradingRequest(BaseModel):
    answer: str = Field(..., description="The reference answer provided by the doctor.")

class RefGradingResponse(BaseModel):
    question_id: str = Field(..., description="Question identifier.")

class GradingRequest(BaseModel):
    question_id: str = Field(..., description="Question identifier.")
    answer: str = Field(..., description="The student's answer to be graded.")
    
    


class GradingResponse(BaseModel):
    final_score: float = Field(..., ge=0, le=1, description="Final weighted score.")
    details: list[dict] = Field(
        ...,
        description="Detailed scoring information for each reference chunk.",
    )

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
    
    
    

