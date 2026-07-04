from fastapi import Depends

from ...states import StepOutput, FailureInfo
from services.lectures.lecture_service import LectureService
from services.summarize.summarize_service import SummarizeService
from core.request_dependencies import get_lecture_service, get_summarize_service
from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)

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
		step_id: str,
		lecture_id: str,
	) -> StepOutput:
		logger.info("[MongoDBTools] get_lecture_whole_content_by_lecture_id START | step_id: %s | lecture_id: %s", step_id, lecture_id)
		lecture_content = await self.lecture_service.get_lecture_content(
			lecture_id
		)

		if lecture_content:
			logger.info("[MongoDBTools] get_lecture_whole_content_by_lecture_id OK | lecture_id: %s | content length: %d",
						lecture_id, len(str(lecture_content)))
			failure_info = None
			content = {
				"lecture_content": lecture_content,
			}
		else:
			logger.info("[MongoDBTools] get_lecture_whole_content_by_lecture_id FAILED | lecture_id: %s not found", lecture_id)
			failure_info = FailureInfo(
				message="Lecture content was not found.",
				clarification_message="Please verify the lecture identifier.",
				explanation="No lecture content exists for the provided lecture ID. Try replanning by resolving the correct lecture ID first if not done. Otherwise, request clarification.",
			)
			content = {}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="get_lecture_whole_content_by_lecture_id",
			tool_args={
				"lecture_id": lecture_id,
			},
			content=content,
			failure_info=failure_info,
		)

	async def get_lecture_summary_by_lecture_id(
		self,
		step_id: str,
		lecture_id: str,
	) -> StepOutput:
		logger.info("[MongoDBTools] get_lecture_summary_by_lecture_id START | step_id: %s | lecture_id: %s", step_id, lecture_id)
		summary = await self.summarize_service.get_summary(
			lecture_id=lecture_id,
			level=2,
		)

		if summary:
			logger.info("[MongoDBTools] get_lecture_summary_by_lecture_id OK | lecture_id: %s | summary length: %d",
						lecture_id, len(str(summary)))
			failure_info = None
			content = {
				"summary": summary,
			}
		else:
			logger.info("[MongoDBTools] get_lecture_summary_by_lecture_id FAILED | lecture_id: %s not found", lecture_id)
			failure_info = FailureInfo(
				message="Lecture summary was not found.",
				clarification_message="Please verify the lecture identifier.",
				explanation="No summary exists for the provided lecture ID. Try replanning by resolving the correct lecture ID first, or request clarification.",
			)
			content = {}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="get_lecture_summary_by_lecture_id",
			tool_args={
				"lecture_id": lecture_id,
			},
			content=content,
			failure_info=failure_info,
		)


def get_mongodb_tools(
	lecture_service: LectureService = Depends(get_lecture_service),
	summarize_service: SummarizeService = Depends(get_summarize_service),
) -> MongoDBTools:
	return MongoDBTools(
		lecture_service=lecture_service,
		summarize_service=summarize_service,
	)