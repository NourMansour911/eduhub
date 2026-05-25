from fastapi import Depends

from services.lectures.lecture_service import LectureService, get_lecture_service
from services.session.session_service import SessionService, get_session_service


class VDBTools:
	def __init__(self, lecture_service: LectureService, session_service: SessionService):
		self.lecture_service = lecture_service
		self.session_service = session_service

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
		return await self.session_service.search_sessions_by_user_id(
			user_id=user_id,
			limit=3,
		)



def get_vdb_tools(
	lecture_service: LectureService = Depends(get_lecture_service),
	session_service: SessionService = Depends(get_session_service),
) -> VDBTools:
	return VDBTools(lecture_service=lecture_service, session_service=session_service)


__all__ = ["VDBTools", "get_vdb_tools"]
