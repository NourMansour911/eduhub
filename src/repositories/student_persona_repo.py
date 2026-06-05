from models import StudentPersonaModel
from enums import DBEnum


class StudentPersonaRepo:

    def __init__(self, db_client: object):
        self.db_client = db_client
        self.collection_name = DBEnum.COLLECTION_STUDENT_PERSONA_NAME.value
        self.collection = self.db_client[self.collection_name]

    @classmethod
    async def create_instance(cls, db_client: object):
        return cls(db_client)

    async def init_collection(self):
        existing_collections = await self.db_client.list_collection_names()
        if self.collection_name not in existing_collections:
            await self.db_client.create_collection(self.collection_name)
  
            for idx in self.get_indexes():
                await self.collection.create_index(idx["key"], name=idx.get("name"), unique=idx.get("unique", False))

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("student_id", 1)],
                "name": "student_id_index_1",
                "unique": True,
            },
        ]

    async def add_persona(self, student_persona: StudentPersonaModel):
        result = await self.collection.insert_one(
            student_persona.model_dump(by_alias=True, exclude_none=True)
        )
        student_persona.iid = result.inserted_id
        return student_persona.iid

    async def get_persona_by_student_id(self, student_id: str) -> StudentPersonaModel | None:
        record = await self.collection.find_one({"student_id": student_id})
        return StudentPersonaModel(**record) if record else None
