from typing import List

from fastapi import Depends

from dtos import RAGContextDTO, VDBSearchResultPayload
from .search_service import SearchService, get_search_service


class VDBTools:
	def __init__(self, search_service: SearchService):
		self.search_service = search_service
		self.source = "vector_db"

	async def ask_in_specific_lecture_by_lecture_id(
		self,
		lecture_id: str,
		query: str,
		threshold: float = 0.4,
	) -> RAGContextDTO:

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
			status = 0
			content = {
				"message": "No relevant information found in the lecture.",
				"clarification_message": "Could you please provide more details or specify your question related to the lecture?",
				"explanation": "No relevant information in the lecture passed the relevance threshold.",
			}
		else:
			status = 1
			content = {
				"retrieved_context": filtered_payload,
			}

		return RAGContextDTO(
			status=status,
			source=self.source,
			tool_name="ask_in_specific_lecture_by_lecture_id",
			tool_args={
				"lecture_id": lecture_id,
				"query": query,
			},
			content=content,
		)

	async def ask_in_the_whole_course_by_course_id(
		self,
		course_id: str,
		query: str,
		threshold: float = 0.4,
	) -> RAGContextDTO:

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
			status = 0
			content = {
				"message": "No relevant information found across the course.",
				"clarification_message": "Could you provide more details or specify the topic within the course?",
				"explanation": "No chunks passed the relevance threshold for this course and query.",
			}
		else:
			status = 1
			content = {
				"retrieved_context": filtered_payload,
			}

		return RAGContextDTO(
			status=status,
			source=self.source,
			tool_name="ask_in_the_whole_course_by_course_id",
			tool_args={
				"course_id": course_id,
				"query": query,
			},
			content=content,
		)

	async def search_in_sessions_history(
		self,
		user_id: str,
		query: str,
		threshold: float = 0.4,
	) -> RAGContextDTO:

		payload: List[VDBSearchResultPayload] = (
			await self.search_service.search_by_metadata_field(
				collection_name="sessions",
				field_name="user_id",
				field_value=user_id,
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
			status = 0
			content = {
				"message": "No relevant session history found.",
				"clarification_message": "Try rephrasing the question or provide more context.",
				"explanation": "No past session chunks matched the query above the relevance threshold.",
			}
		else:
			status = 1
			content = {
				"retrieved_context": filtered_payload,
			}

		return RAGContextDTO(
			status=status,
			source=self.source,
			tool_name="search_in_sessions_history",
			tool_args={
				"user_id": user_id,
				"query": query,
			},
			content=content,
		)

	async def ask_in_legal_regulations(
		self,
		query: str,
		threshold: float = 0.4,
	) -> RAGContextDTO:

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
			status = 0
			content = {
				"message": "No relevant legal/regulatory content found.",
				"clarification_message": "Try giving more context or a regulation code if known.",
				"explanation": "No regulatory chunks passed the relevance threshold for this query.",
			}
		else:
			status = 1
			content = {
				"retrieved_context": filtered_payload,
			}

		return RAGContextDTO(
			status=status,
			source=self.source,
			tool_name="ask_in_legal_regulations",
			tool_args={
				"query": query,
			},
			content=content,
		)


def get_vdb_tools(
	search_service: SearchService = Depends(get_search_service),
) -> VDBTools:
	return VDBTools(search_service=search_service)