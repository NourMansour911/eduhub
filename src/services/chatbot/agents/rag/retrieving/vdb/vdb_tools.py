from fastapi import Depends

from services.lectures.lecture_service import LectureService, get_lecture_service

from .search_service import SearchService, get_search_service


class VDBTools:
	def __init__(self, lecture_service: LectureService, search_service: SearchService):
		self.lecture_service = lecture_service
		self.search_service = search_service

	async def search_lectures_by_lecture_id(self, lecture_id: str):
		return await self.lecture_service.search_lectures_by_lecture_id(
			lecture_id=lecture_id,
			limit=3,
		)

	async def search_lectures_by_subject_id(self, subject_id: str):
		return await self.lecture_service.search_lectures_by_subject_id(
			subject_id=subject_id,
			limit=5,
		)

	async def search_sessions_by_user_id(self, user_id: str):
		return await self.search_service.search_by_metadata_field(
			collection_name="sessions",
			field_name="user_id",
			field_value=user_id,
			limit=3,
		)

	async def search_sessions_by_archived_at_range(self, gte: str, lte: str):
		return await self.search_service.search_by_metadata_range(
			collection_name="sessions",
			field_name="archived_at",
			gte=gte,
			lte=lte,
			limit=3,
		)


def get_vdb_tools(
	lecture_service: LectureService = Depends(get_lecture_service),
	search_service: SearchService = Depends(get_search_service),
) -> VDBTools:
	return VDBTools(lecture_service=lecture_service, search_service=search_service)


__all__ = ["VDBTools", "get_vdb_tools"]