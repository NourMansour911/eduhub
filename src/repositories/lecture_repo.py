from models import LectureModel
from enums import DBEnum
from bson import ObjectId


class LectureRepo:

    def __init__(self, db_client: object):
        self.db_client = db_client
        self.collection_name = DBEnum.COLLECTION_LECTURE_NAME.value
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
                "key": [("course_id", 1)],
                "name": "course_id_index_1",
                "unique": False,
            },
            {
                "key": [("lecture_id", 1)],
                "name": "lecture_id_index_1",
                "unique": True,
            },
        ]

    async def add_lecture(self, lecture: LectureModel):
        result = await self.collection.insert_one(
            lecture.model_dump(by_alias=True, exclude_none=True)
        )
        lecture.iid = result.inserted_id
        return lecture.iid


    async def get_lecture_by_lecture_id(self, lecture_id: str) -> LectureModel | None:
        record = await self.collection.find_one({"lecture_id": lecture_id})
        return LectureModel(**record) if record else None

    async def delete_by_lecture_id(self, lecture_id: str) -> int:

        result = await self.collection.delete_one({"lecture_id": lecture_id})
        return int(result.deleted_count)

    async def delete_by_course_id(self, course_id: str) -> int:

        sid = ObjectId(course_id) if isinstance(course_id, str) and ObjectId.is_valid(course_id) else course_id
        result = await self.collection.delete_many({"course_id": sid})
        return int(result.deleted_count)

    async def get_lectures_by_course(self, course_id: str) -> list[LectureModel]:

        cursor = self.collection.find({"course_id": course_id}).sort("order", 1)
        results = []
        async for doc in cursor:
            results.append(LectureModel(**doc))
        return results
