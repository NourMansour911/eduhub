from fastapi import Depends

from dtos import RAGContextDTO
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
		self.source = "mongodb"

	async def get_lecture_whole_content_by_lecture_id(
		self,
		lecture_id: str,
	) -> RAGContextDTO:

		lecture_content = await self.lecture_service.get_lecture_content(
			lecture_id
		)

		if lecture_content:
			status = 1
			content = {
				"lecture_content": lecture_content,
			}
		else:
			status = 0
			content = {
				"message": "Lecture content was not found.",
				"clarification_message": "Please verify the lecture identifier.",
				"explanation": "No lecture content exists for the provided lecture ID.",
			}

		return RAGContextDTO(
			status=status,
			source=self.source,
			tool_name="get_lecture_whole_content_by_lecture_id",
			tool_args={
				"lecture_id": lecture_id,
			},
			content=content,
		)

	async def get_lecture_summary_by_lecture_id(
		self,
		lecture_id: str,
	) -> RAGContextDTO:

		summary = await self.summarize_service.get_summary(
			lecture_id=lecture_id,
			level=2,
		)

		if summary:
			status = 1
			content = {
				"summary": summary,
			}
		else:
			status = 0
			content = {
				"message": "Lecture summary was not found.",
				"clarification_message": "Please verify the lecture identifier.",
				"explanation": "No summary exists for the provided lecture ID.",
			}

		return RAGContextDTO(
			status=status,
			source=self.source,
			tool_name="get_lecture_summary_by_lecture_id",
			tool_args={
				"lecture_id": lecture_id,
			},
			content=content,
		)


def get_mongodb_tools(
	lecture_service: LectureService = Depends(get_lecture_service),
	summarize_service: SummarizeService = Depends(get_summarize_service),
) -> MongoDBTools:
	return MongoDBTools(
		lecture_service=lecture_service,
		summarize_service=summarize_service,
	)