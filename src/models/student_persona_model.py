from pydantic import Field

from models.mongo_document_model import MongoDocumentModel


class StudentPersonaModel(MongoDocumentModel):
    student_id: str = Field(..., description="The unique identifier for the student")
    persona: str = Field(..., description="The persona or profile details of the student, e.g. academic level, tone preferences, etc.")
