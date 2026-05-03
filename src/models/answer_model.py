
from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId
from datetime import datetime

class AnswerModel(BaseModel):
    iid: Optional[ObjectId] = Field(None, alias="_id")
    text: str = Field(..., description="Text of the answer")
    created_at: datetime = Field(default_factory=datetime.now)
    word_count: int = Field(..., description="Word count in chunk")

    
    
    model_config = {  
        "arbitrary_types_allowed": True, 
        "populate_by_name": True,
        "json_encoders": {ObjectId: str}   
    }
