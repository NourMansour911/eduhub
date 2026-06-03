from typing import Any

from fastapi import Depends

from core.request_dependencies import get_embedding_client
from integrations.llm import LLMInterface

from dtos import RAGContextDTO, FailureInfo
from .name_resolver import NameResolver
from .sql_server_calling import SqlServerCalling


class SQLTools:
	def __init__(self, embedding_client: LLMInterface):
		self.embedding_client = embedding_client
		self.name_resolver = NameResolver(embedding_client)
		self.sql_server_calling = SqlServerCalling()
		self.source = "sql_server"

	async def get_course_id_by_course_name(
		self,
		student_id: str,
		course_name: str,
	) -> RAGContextDTO:

		courses = self.sql_server_calling.get_student_courses(student_id)

		resolved_course = await self.name_resolver.resolve_best_match_with_threshold(
			items=courses,
			query_name=course_name,
			name_key="name",
			id_key="course_id",
			threshold=0.3,
		)

		if resolved_course is None:
			failure_info = FailureInfo(
				message="No matching course was found.",
				clarification_message="Please provide the course name more accurately.",
				explanation="The requested course could not be matched against the student's enrolled courses.",
			)
			content = {}
		else:
			failure_info = None
			content = {
				"course_id": resolved_course["id"],
				"course_name": resolved_course["name"],
			}

		return RAGContextDTO(
			source=self.source,
			tool_name="get_course_id_by_course_name",
			tool_args={
				"student_id": student_id,
				"course_name": course_name,
			},
			content=content,
			failure_info=failure_info,
		)

	async def get_lecture_id_by_lecture_name(
		self,
		course_id: str,
		lecture_name: str,
	) -> RAGContextDTO:

		lectures = self.sql_server_calling.get_course_lectures(course_id)

		resolved_lecture = await self.name_resolver.resolve_best_match_with_threshold(
			items=lectures,
			query_name=lecture_name,
			name_key="title",
			id_key="id",
			threshold=0.3,
		)

		if resolved_lecture is None:
			failure_info = FailureInfo(
				message="No matching lecture was found.",
				clarification_message="Please provide the lecture name more accurately.",
				explanation="The requested lecture could not be matched against the lectures available in the course.",
			)
			content = {}
		else:
			failure_info = None
			content = {
				"lecture_id": resolved_lecture["id"],
				"lecture_name": resolved_lecture["title"],
			}

		return RAGContextDTO(
			source=self.source,
			tool_name="get_lecture_id_by_lecture_name",
			tool_args={
				"course_id": course_id,
				"lecture_name": lecture_name,
			},
			content=content,
			failure_info=failure_info,
		)

	async def get_course_details_by_course_id(
		self,
		course_id: str,
	) -> RAGContextDTO:

		course_details = self.sql_server_calling.get_course_details(course_id)

		if not course_details:
			failure_info = FailureInfo(
				message="Course details were not found.",
				clarification_message="Please verify the course identifier.",
				explanation="No course record exists for the provided course ID.",
			)
			content = {}
		else:
			failure_info = None
			content = course_details

		return RAGContextDTO(
			source=self.source,
			tool_name="get_course_details_by_course_id",
			tool_args={
				"course_id": course_id,
			},
			content=content,
			failure_info=failure_info,
		)

	async def get_all_student_courses_ids_and_names(
		self,
		student_id: str,
	) -> RAGContextDTO:

		courses: list[dict[str, Any]] = (
			self.sql_server_calling.get_student_courses(student_id)
		)

		if not courses:
			failure_info = FailureInfo(
				message="No courses were found for this student.",
				clarification_message="Please verify the student identifier.",
				explanation="The student is not enrolled in any courses or the student record was not found.",
			)
			content = {}
		else:
			failure_info = None
			content = {
				"courses": courses,
			}

		return RAGContextDTO(
			source=self.source,
			tool_name="get_all_student_courses_ids_and_names",
			tool_args={
				"student_id": student_id,
			},
			content=content,
			failure_info=failure_info,
		)


def get_sql_tools(
	embedding_client: LLMInterface = Depends(get_embedding_client),
) -> SQLTools:
	return SQLTools(embedding_client=embedding_client)