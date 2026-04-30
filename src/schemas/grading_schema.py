from pydantic import BaseModel, Field




class RefGradingRequest(BaseModel):
    answer: str = Field(..., description="The reference answer provided by the doctor.")

class RefGradingResponse(BaseModel):
    question_id: str = Field(..., description="Question identifier.")

class GradingRequest(BaseModel):
    question_id: str = Field(..., description="Question identifier.")
    student_answer: str = Field(..., description="The student's answer to be graded.")
    
    
class GradingResponse(BaseModel):
    degree: float = Field(
        ...,
        ge=0,
        le=100,
        description="The similarity percentage between the student's answer and the reference answer.",
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
    
    
    

