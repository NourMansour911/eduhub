
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class AnswerModel(BaseModel):
    iid: Optional[str] = Field(None, alias="_id")
    question: str = Field(..., description="The question text")
    text: str = Field(..., description="Text of the answer")
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("iid", mode="before")
    @classmethod
    def parse_iid(cls, value):
        if value is None:
            return value
        return str(value)

    
    
    model_config = {  
        "arbitrary_types_allowed": True, 
        "populate_by_name": True,
    }
