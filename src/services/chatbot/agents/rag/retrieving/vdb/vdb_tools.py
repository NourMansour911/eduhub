from typing import List

from fastapi import Depends

from dtos.vdb_payload_dto import VDBSearchResultPayload
from ...states import StepOutput, FailureInfo
from .search_service import SearchService, get_search_service
from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


class VDBTools:
	def __init__(self, search_service: SearchService):
		self.search_service = search_service
		self.source = "vector_db"

	async def ask_in_specific_lecture_by_lecture_id(
		self,
		step_id: str,
		lecture_id: str,
		query: str,
		threshold: float = 0.35,
	) -> StepOutput:
		logger.info(
			"Tool ask_in_specific_lecture_by_lecture_id started. step_id: %s, lecture_id: %s, query: %s",
			step_id,
			lecture_id,
			query,
		)

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="lectures",
				field_name="lecture_id",
				field_value=lecture_id,
				limit=3,
				query_text=query,
				rewrite_mode="lecture_search",
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		logger.info(
			"Tool ask_in_specific_lecture_by_lecture_id search completed. Found %d items, %d items passed threshold (%f)",
			len(payload),
			len(filtered_payload),
			threshold,
		)

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant information found in the lecture.",
				clarification_message="Could you please provide more details or specify your question related to the lecture?",
				explanation="No relevant information in the lecture passed the relevance threshold. If the query was too specific or narrow, try replanning to search the whole course instead of this specific lecture, or use a broader/different query. If no other options are viable, route to clarification.",
			)
			content = {}
		else:
			failure_info = None
			content = {
				"retrieved_context": filtered_payload,
			}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="ask_in_specific_lecture_by_lecture_id",
			tool_args={
				"lecture_id": lecture_id,
				"query": query,
			},
			content=content,
			failure_info=failure_info,
		)

	async def ask_in_the_whole_course_by_course_id(
		self,
		step_id: str,
		course_id: str,
		query: str,
		threshold: float = 0.35,
	) -> StepOutput:
		logger.info(
			"Tool ask_in_the_whole_course_by_course_id started. step_id: %s, course_id: %s, query: %s",
			step_id,
			course_id,
			query,
		)

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="lectures",
				field_name="course_id",
				field_value=course_id,
				limit=5,
				query_text=query,
				rewrite_mode="lecture_search",
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		logger.info(
			"Tool ask_in_the_whole_course_by_course_id search completed. Found %d items, %d items passed threshold (%f)",
			len(payload),
			len(filtered_payload),
			threshold,
		)

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant information found across the course.",
				clarification_message="Could you provide more details or specify the topic within the course?",
				explanation="No chunks passed the relevance threshold for this course and query. Try replanning with a different query phrasing or search terms. If already attempted, request clarification.",
			)
			content = {}
		else:
			failure_info = None
			content = {
				"retrieved_context": filtered_payload,
			}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="ask_in_the_whole_course_by_course_id",
			tool_args={
				"course_id": course_id,
				"query": query,
			},
			content=content,
			failure_info=failure_info,
		)

	async def search_in_sessions_history(
		self,
		step_id: str,
		student_id: str,
		query: str,
		threshold: float = 0.2,
	) -> StepOutput:
		logger.info(
			"Tool search_in_sessions_history started. step_id: %s, student_id: %s, query: %s",
			step_id,
			student_id,
			query,
		)

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="sessions",
				field_name="user_id",
				field_value=student_id,
				limit=3,
				query_text=query,
				rewrite_mode="session_summary",
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		logger.info(
			"Tool search_in_sessions_history completed. Found %d items, %d items passed threshold (%f)",
			len(payload),
			len(filtered_payload),
			threshold,
		)

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant session history found.",
				clarification_message="Try rephrasing the question or provide more context.",
				explanation="No past session chunks matched the query above the relevance threshold. Try replanning by querying student courses or regulations if relevant, or request clarification.",
			)
			content = {}
		else:
			failure_info = None
			content = {
				"retrieved_context": filtered_payload,
			}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="search_in_sessions_history",
			tool_args={
				"user_id": student_id,
				"query": query,
			},
			content=content,
			failure_info=failure_info,
		)

	async def ask_in_legal_regulations(
		self,
		step_id: str,
		query: str,
		threshold: float = 0.4,
	) -> StepOutput:
		logger.info(
			"Tool ask_in_legal_regulations started. step_id: %s, query: %s",
			step_id,
			query,
		)

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="lectures",
				field_name="course_id",
				field_value="REG01",
				limit=5,
				query_text=query,
				rewrite_mode="regulations_search",
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		logger.info(
			"Tool ask_in_legal_regulations completed. Found %d items, %d items passed threshold (%f)",
			len(payload),
			len(filtered_payload),
			threshold,
		)

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant legal/regulatory content found.",
				clarification_message="Try giving more context or a regulation code if known.",
				explanation="No regulatory chunks passed the relevance threshold for this query. If the query could be academic rather than regulatory, try replanning to search the course or lectures. Otherwise, request clarification.",
			)
			content = {}
		else:
			failure_info = None
			content = {
				"retrieved_context": filtered_payload,
			}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="ask_in_legal_regulations",
			tool_args={
				"query": query,
			},
			content=content,
			failure_info=failure_info,
		)


def get_vdb_tools(
	search_service: SearchService = Depends(get_search_service),
) -> VDBTools:
	return VDBTools(search_service=search_service)