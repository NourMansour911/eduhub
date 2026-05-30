

from typing import Any


class SqlServerCalling:
     
	@staticmethod
	def get_course_details(course_id: str) -> dict[str, Any]:
		return {
			"course_id": course_id,
			"doctor_name": "Admin One",
			"hours": 4,
			"price": 1500,
		}

	@staticmethod
	def get_student_courses(student_id: str) -> list[dict[str, Any]]:
		return [
			{"course_id": "course1", "name": "Database Systems", "student_id": student_id},
			{"course_id": "course2", "name": "Data Science", "student_id": student_id},
		]

	@staticmethod
	def get_course_lectures(course_id: str) -> list[dict[str, Any]]:
		return [
			{
				"id": 1,
				"course_id": course_id,
				"title": "lec 1",
			},
			{
				"id": 2,
				"course_id": course_id,
				"title": "dawdawd",
			},
		]