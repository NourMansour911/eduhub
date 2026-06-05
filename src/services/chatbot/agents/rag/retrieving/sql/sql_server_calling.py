

from typing import Any


class SqlServerCalling:
     
	@staticmethod
	def get_course_details(course_id: str) -> dict[str, Any]:
		return {
			"course_id": course_id,
			"doctor_name": "Doctor One",
			"hours": 4,
			"price": 1500,
		}

	@staticmethod
	def get_student_courses(student_id: str) -> list[dict[str, Any]]:
		return [
			{"course_id": "IS422P", "name": "Data Mining"},
			{"course_id": "HCI_T01", "name": "Human Computer Interaction"},
		]

	@staticmethod
	def get_course_lectures(course_id: str) -> list[dict[str, Any]]:
		return [
			{
				"id": "1RYCZiRS0DsISSz-o_0heUrKFTDcvIOxZ",
				"title": "Usability",
			},
			{
				"id": "1wYJY2YK3_xH36iaPZIcXdUHm_eemDWtc",
				"title": "Navigation,Signposts, and Wayfinding",
			},
		]