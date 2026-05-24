from fastapi import Depends

from services.vdb_service import VDBService, get_vdb_service


class VDBTools:
	def __init__(self, vdb_service: VDBService):
		self.vdb_service = vdb_service

	async def search_lectures_by_lecture_id(self, lecture_id: str, limit: int = 10):
		return await self.vdb_service.search_lectures_by_lecture_id(
			lecture_id=lecture_id,
			limit=limit,
		)

	async def search_lectures_by_subject_id(self, subject_id: str, limit: int = 10):
		return await self.vdb_service.search_lectures_by_subject_id(
			subject_id=subject_id,
			limit=limit,
		)

	async def search_sessions_by_user_id(self, user_id: str, limit: int = 10):
		return await self.vdb_service.search_sessions_by_user_id(
			user_id=user_id,
			limit=limit,
		)

	async def search_sessions_by_archived_at_range(self, gte: str, lte: str, limit: int = 10):
		return await self.vdb_service.search_sessions_by_archived_at_range(
			gte=gte,
			lte=lte,
			limit=limit,
		)


def get_vdb_tools(
	vdb_service: VDBService = Depends(get_vdb_service),
) -> VDBTools:
	return VDBTools(vdb_service=vdb_service)


__all__ = ["VDBTools", "get_vdb_tools"]
