
from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId
from datetime import datetime

class AnswerModel(BaseModel):
    iid: Optional[ObjectId] = Field(None, alias="_id")
    question: str = Field(..., description="The question text")
    text: str = Field(..., description="Text of the answer")
    created_at: datetime = Field(default_factory=datetime.now)

    
    
    model_config = {  
        "arbitrary_types_allowed": True, 
        "populate_by_name": True,
        "json_encoders": {ObjectId: str}   
    }
