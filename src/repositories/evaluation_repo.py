from typing import Optional, List
from models.evaluation_model import EvaluationModel, EvaluationMetricsLayer
from enums.db_enum import DBEnum

class EvaluationRepo:
    def __init__(self, db_client: object):
        self.db_client = db_client
        self.collection_name = DBEnum.COLLECTION_EVAL_SESSION_NAME.value
        self.collection = self.db_client[self.collection_name]

    @classmethod
    async def create_instance(cls, db_client: object):
        return cls(db_client)

    async def init_collection(self):
        existing_collections = await self.db_client.list_collection_names()
        if self.collection_name not in existing_collections:
            await self.db_client.create_collection(self.collection_name)

    async def add_eval_session(self, doc: EvaluationModel) -> str:
        result = await self.collection.insert_one(
            doc.model_dump(by_alias=True, exclude_none=True)
        )
        doc.iid = str(result.inserted_id)
        return doc.iid

    async def update_evaluation_results(self, session_id: str, eval_data: EvaluationMetricsLayer) -> bool:
        from bson import ObjectId
        result = await self.collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"evaluation": eval_data.model_dump(exclude_none=True)}}
        )
        return result.modified_count > 0

    async def get_unevaluated_sessions(self, limit: int = 100) -> List[EvaluationModel]:
        cursor = self.collection.find({"evaluation.is_evaluated": False}).limit(limit)
        sessions = []
        async for doc in cursor:
            sessions.append(EvaluationModel.model_validate(doc))
        return sessions
