from typing import Any, Optional

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator


class MongoDocumentModel(BaseModel):
    iid: Optional[str] = Field(None, alias="_id")

    @field_validator("iid", mode="before")
    @classmethod
    def normalize_iid(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, ObjectId):
            return str(value)
        return str(value)

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }