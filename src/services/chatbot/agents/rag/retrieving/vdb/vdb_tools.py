from fastapi import Depends

from .search_service import SearchService, get_search_service


class VDBTools:
	def __init__(self, search_service: SearchService):
		self.search_service = search_service

	async def ask_in_specific_lecture_by_lecture_id(self, lecture_id: str, query: str):
		return await self.search_service.search_by_metadata_field(
			collection_name="lectures",
			field_name="lecture_id",
			field_value=lecture_id,
			limit=3,
			query_text=query,
		)

	async def ask_in_the_whole_course_by_course_id(self, course_id: str, query: str):
		return await self.search_service.search_by_metadata_field(
			collection_name="lectures",
			field_name="course_id",
			field_value=course_id,
			limit=5,
			query_text=query,
		)

	async def search_in_sessions_history(self, user_id: str,query: str):
		return await self.search_service.search_by_metadata_field(
			collection_name="sessions",
			field_name="user_id",
			field_value=user_id,
			limit=3,
			query_text=query,
		)

	async def ask_in_legal_regulations(self, query: str):
		return await self.search_service.search_by_metadata_field(
			collection_name="lectures",
			field_name="course_id",
			field_value="REG01",
			limit=5,
			query_text=query,
		)





def get_vdb_tools(
	search_service: SearchService = Depends(get_search_service),
) -> VDBTools:
	return VDBTools(search_service=search_service)


__all__ = ["VDBTools", "get_vdb_tools"]