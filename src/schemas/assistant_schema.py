from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    lecture_id: str = Field(..., description="Lecture identifier to summarize")
    length: int = Field(..., ge=0, le=2, description="Summary length level: 0 (short),1 (medium),2 (long)")


class SummarizeResponse(BaseModel):
    summary: str = Field(..., description="Generated summary text")

class ChatRequest(BaseModel):
    message: str = Field(..., description="Message to send to the chat")
    
class ChatResponse(BaseModel):
    ai_response: str = Field(..., description="Generated chat response")