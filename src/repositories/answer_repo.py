from models import AnswerModel
from enums import DBEnum
from bson import ObjectId


class AnswerRepo:

    def __init__(self, db_client: object):
        self.db_client = db_client
        self.collection_name = DBEnum.COLLECTION_ANSWER_NAME.value
        self.collection = self.db_client[self.collection_name]

    @classmethod
    async def create_instance(cls, db_client: object):
        return cls(db_client)

    async def init_collection(self):
        existing_collections = await self.db_client.list_collection_names()
        if self.collection_name not in existing_collections:
            await self.db_client.create_collection(self.collection_name)

    async def add_answer(self, answer: AnswerModel):
        result = await self.collection.insert_one(
            answer.model_dump(by_alias=True, exclude_none=True)
        )
        answer.iid = result.inserted_id
        return answer.iid

    async def get_answer(self, iid: str) -> AnswerModel | None:
        oid = ObjectId(iid) if isinstance(iid, str) else iid
        record = await self.collection.find_one({"_id": oid})
        return AnswerModel(**record) if record else None
