from typing import Any, Optional

from fastapi import Depends

from core.request_dependencies import get_embedding_client
from integrations.llm import LLMInterface

from .name_resolver import NameResolver
from .sql_server_calling import SqlServerCalling


class SQLTools:
	def __init__(self, embedding_client: LLMInterface):
		self.embedding_client = embedding_client
		self.name_resolver = NameResolver(embedding_client)
		self.sql_server_calling = SqlServerCalling()

	async def get_course_id_by_course_name(self, student_id: str, course_name: str) -> Optional[dict[str, Any]]:
		courses = self.sql_server_calling.get_student_courses(student_id)
		resolved_course = await self.name_resolver.resolve_best_match_with_threshold(
			items=courses,
			query_name=course_name,
			name_key="name",
			id_key="course_id",
			threshold=0,
		)
		
		if resolved_course is not None:
			return resolved_course
		
		return {
			"course_id": resolved_course["id"],
			"course_name": resolved_course["name"],
		}

	async def get_lecture_id_by_lecture_name(self, course_id: str, lecture_name: str) -> Optional[dict[str, Any]]:
		lectures = self.sql_server_calling.get_course_lectures(course_id)
		resolved_lecture = await self.name_resolver.resolve_best_match_with_threshold(
			items=lectures,
			query_name=lecture_name,
			name_key="title",
			id_key="id",
			threshold=0,
		)
		
		if resolved_lecture is not None:
			return resolved_lecture
		
		return {
			"lecture_id": resolved_lecture["id"],
			"lecture_name": resolved_lecture["title"],
		}
	
	
	async def get_course_details_by_course_id(self, course_id: str) -> Optional[dict[str, Any]]:
		return self.sql_server_calling.get_course_details(course_id)

	
	async def get_all_student_courses_ids_and_names(self, student_id: str) -> list[dict[str, Any]]:
		return self.sql_server_calling.get_student_courses(student_id)


def get_sql_tools(embedding_client: LLMInterface = Depends(get_embedding_client)) -> SQLTools:
	return SQLTools(embedding_client=embedding_client)

