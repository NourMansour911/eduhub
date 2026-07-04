from typing import Any

from fastapi import Depends

from core.request_dependencies import get_embedding_client
from integrations.llm import LLMInterface

from ...states import StepOutput, FailureInfo
from .name_resolver import NameResolver
from .sql_server_calling import SqlServerCalling
from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


class SQLTools:
	def __init__(self, embedding_client: LLMInterface, sql_server_calling: SqlServerCalling):
		self.embedding_client = embedding_client
		self.name_resolver = NameResolver(embedding_client)
		self.sql_server_calling = sql_server_calling
		self.source = "sql_server"

	async def get_course_id_by_course_name(
		self,
		step_id: str,
		student_id: str,
		course_name: str,
	) -> StepOutput:
		logger.info("[SQLTools] get_course_id_by_course_name START | step_id: %s | student_id: %s | course_name: '%s'",
					step_id, student_id, course_name)
		try:
			courses = await self.sql_server_calling.get_student_courses(student_id)

			resolved_course = await self.name_resolver.resolve_best_match_with_threshold(
				items=courses,
				query_name=course_name,
				name_key="name",
				id_key="course_id",
				threshold=0.3,
			)

			if resolved_course is None:
				logger.info("[SQLTools] get_course_id_by_course_name FAILED | no match for '%s' among %d courses", course_name, len(courses))
				failure_info = FailureInfo(
					message="No matching course was found.",
					clarification_message="Please provide the course name more accurately.",
					explanation="The requested course could not be matched against the student's enrolled courses.",
				)
				content = {}
			else:
				logger.info("[SQLTools] get_course_id_by_course_name OK | resolved: %s (id=%s)",
							resolved_course.get('name'), resolved_course.get('id'))
				failure_info = None
				content = {
					"course_id": resolved_course["id"],
					"course_name": resolved_course["name"],
				}
		except Exception as exc:
			logger.error("[SQLTools] get_course_id_by_course_name EXCEPTION | step_id: %s | error: %s", step_id, exc)
			failure_info = FailureInfo(
				message="Database temporarily down.",
				clarification_message="We cannot check your enrolled courses right now. Please try again later.",
				explanation=str(exc),
			)
			content = {}

		return StepOutput(
			step_id=step_id,
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
		step_id: str,
		course_id: str,
		lecture_name: str,
	) -> StepOutput:
		logger.info("[SQLTools] get_lecture_id_by_lecture_name START | step_id: %s | course_id: %s | lecture_name: '%s'",
					step_id, course_id, lecture_name)
		try:
			lectures = await self.sql_server_calling.get_course_lectures(course_id)

			resolved_lecture = await self.name_resolver.resolve_best_match_with_threshold(
				items=lectures,
				query_name=lecture_name,
				name_key="title",
				id_key="id",
				threshold=0.3,
			)

			if resolved_lecture is None:
				logger.info("[SQLTools] get_lecture_id_by_lecture_name FAILED | no match for '%s' among %d lectures", lecture_name, len(lectures))
				failure_info = FailureInfo(
					message="No matching lecture was found.",
					clarification_message="Please provide the lecture name more accurately.",
					explanation="The requested lecture could not be matched against the lectures available in the course.",
				)
				content = {}
			else:
				logger.info("[SQLTools] get_lecture_id_by_lecture_name OK | resolved: '%s' (id=%s)",
							resolved_lecture.get('title') or resolved_lecture.get('name'), resolved_lecture.get('id'))
				failure_info = None
				content = {
					"lecture_id": resolved_lecture["id"],
					"lecture_name": resolved_lecture["title"],
				}
		except Exception as exc:
			logger.error("[SQLTools] get_lecture_id_by_lecture_name EXCEPTION | step_id: %s | error: %s", step_id, exc)
			failure_info = FailureInfo(
				message="Database temporarily down.",
				clarification_message="We cannot check lectures right now. Please try again later.",
				explanation=str(exc),
			)
			content = {}

		return StepOutput(
			step_id=step_id,
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
		step_id: str,
		course_id: str,
	) -> StepOutput:
		logger.info("[SQLTools] get_course_details_by_course_id START | step_id: %s | course_id: %s", step_id, course_id)
		try:
			course_details = await self.sql_server_calling.get_course_details(course_id)

			if not course_details:
				logger.info("[SQLTools] get_course_details_by_course_id FAILED | course_id: %s not found", course_id)
				failure_info = FailureInfo(
					message="Course details were not found.",
					clarification_message="Please verify the course identifier.",
					explanation="No course record exists for the provided course ID.",
				)
				content = {}
			else:
				logger.info("[SQLTools] get_course_details_by_course_id OK | course_id: %s | keys: %s",
							course_id, list(course_details.keys()) if isinstance(course_details, dict) else type(course_details).__name__)
				failure_info = None
				content = course_details
		except Exception as exc:
			logger.error("[SQLTools] get_course_details_by_course_id EXCEPTION | step_id: %s | error: %s", step_id, exc)
			failure_info = FailureInfo(
				message="Database temporarily down.",
				clarification_message="We cannot check course details right now. Please try again later.",
				explanation=str(exc),
			)
			content = {}

		return StepOutput(
			step_id=step_id,
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
		step_id: str,
		student_id: str,
	) -> StepOutput:

		try:
			courses: list[dict[str, Any]] = (
				await self.sql_server_calling.get_student_courses(student_id)
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
		except Exception as exc:
			failure_info = FailureInfo(
				message="Database temporarily down.",
				clarification_message="We cannot retrieve your courses right now. Please try again later.",
				explanation=str(exc),
			)
			content = {}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="get_all_student_courses_ids_and_names",
			tool_args={
				"student_id": student_id,
			},
			content=content,
			failure_info=failure_info,
		)

	async def get_all_course_lectures_by_course_id(
		self,
		step_id: str,
		course_id: str,
	) -> StepOutput:
		logger.info("[SQLTools] get_all_course_lectures_by_course_id START | step_id: %s | course_id: %s", step_id, course_id)
		try:
			lectures = await self.sql_server_calling.get_course_lectures(course_id)

			if not lectures:
				logger.info("[SQLTools] get_all_course_lectures_by_course_id FAILED | no lectures for course_id: %s", course_id)
				failure_info = FailureInfo(
					message="No lectures were found for this course.",
					clarification_message="Please verify the course identifier.",
					explanation="No lectures exist for the given course ID.",
				)
				content = {}
			else:
				logger.info("[SQLTools] get_all_course_lectures_by_course_id OK | course_id: %s | lectures: %d", course_id, len(lectures))
				failure_info = None
				content = {
					"lectures": lectures,
				}
		except Exception as exc:
			logger.error("[SQLTools] get_all_course_lectures_by_course_id EXCEPTION | step_id: %s | error: %s", step_id, exc)
			failure_info = FailureInfo(
				message="Database temporarily down.",
				clarification_message="We cannot retrieve lectures right now. Please try again later.",
				explanation=str(exc),
			)
			content = {}

		return StepOutput(
			step_id=step_id,
			source=self.source,
			tool_name="get_all_course_lectures_by_course_id",
			tool_args={
				"course_id": course_id,
			},
			content=content,
			failure_info=failure_info,
		)


def get_sql_tools(
	embedding_client: LLMInterface = Depends(get_embedding_client),
) -> SQLTools:
	return SQLTools(embedding_client=embedding_client)