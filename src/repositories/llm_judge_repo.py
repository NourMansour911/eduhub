from models import LLMJudgeInputModel
from enums import DBEnum


class LLMJudgeRepo:

    def __init__(self, db_client: object):
        self.db_client = db_client
        self.collection_name = DBEnum.COLLECTION_LLM_JUDGE_NAME.value
        self.collection = self.db_client[self.collection_name]

    @classmethod
    async def create_instance(cls, db_client: object):
        return cls(db_client)

    async def init_collection(self):
        existing_collections = await self.db_client.list_collection_names()
        if self.collection_name not in existing_collections:
            await self.db_client.create_collection(self.collection_name)

    async def add_judge_input(self, doc: LLMJudgeInputModel) -> str:
        result = await self.collection.insert_one(
            doc.model_dump(by_alias=True, exclude_none=True)
        )
        doc.iid = str(result.inserted_id)
        return doc.iid
