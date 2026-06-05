from typing import List

from fastapi import Depends

from dtos import VDBSearchResultPayload
from ...states import StepOutput, FailureInfo
from .search_service import SearchService, get_search_service


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

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="lectures",
				field_name="lecture_id",
				field_value=lecture_id,
				limit=3,
				query_text=query,
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant information found in the lecture.",
				clarification_message="Could you please provide more details or specify your question related to the lecture?",
				explanation="No relevant information in the lecture passed the relevance threshold.",
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

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="lectures",
				field_name="course_id",
				field_value=course_id,
				limit=5,
				query_text=query,
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant information found across the course.",
				clarification_message="Could you provide more details or specify the topic within the course?",
				explanation="No chunks passed the relevance threshold for this course and query.",
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

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="sessions",
				field_name="user_id",
				field_value=student_id,
				limit=3,
				query_text=query,
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant session history found.",
				clarification_message="Try rephrasing the question or provide more context.",
				explanation="No past session chunks matched the query above the relevance threshold.",
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

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="lectures",
				field_name="course_id",
				field_value="REG01",
				limit=5,
				query_text=query,
			)
		)

		filtered_payload = [
			item.model_dump()
			for item in payload
			if (item.relevance_score or 0) >= threshold
		]

		if not filtered_payload:
			failure_info = FailureInfo(
				message="No relevant legal/regulatory content found.",
				clarification_message="Try giving more context or a regulation code if known.",
				explanation="No regulatory chunks passed the relevance threshold for this query.",
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