from fastapi import Depends

from services.lectures import LectureService, get_lecture_service
from services.summarize import SummarizeService, get_summarize_service


class MongoDBTools:
	def __init__(
		self,
		lecture_service: LectureService,
		summarize_service: SummarizeService,
	):
		self.lecture_service = lecture_service
		self.summarize_service = summarize_service

	async def get_lecture_content(self, lecture_id: str) -> str:
		return await self.lecture_service.get_lecture_content(lecture_id)

	async def get_lecture_summary(self, lecture_id: str, level: int) -> str:
		return await self.summarize_service.get_summary(lecture_id, level)


def get_mongodb_tools(
	lecture_service: LectureService = Depends(get_lecture_service),
	summarize_service: SummarizeService = Depends(get_summarize_service),
) -> MongoDBTools:
	return MongoDBTools(
		lecture_service=lecture_service,
		summarize_service=summarize_service,
	)


__all__ = ["MongoDBTools", "get_mongodb_tools"]