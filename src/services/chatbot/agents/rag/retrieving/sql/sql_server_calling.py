

from typing import Any


import httpx
from helpers.logger import get_logger

logger = get_logger(__name__)

class SqlServerCalling:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_course_details(self, course_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/get_course_details.php"
        params = {"course_id": course_id}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching course details: {e}")
            return {}

    async def get_student_courses(self, student_id: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/get_student_courses.php"
        params = {"student_id": student_id}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching student courses: {e}")
            return []

    async def get_course_lectures(self, course_id: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/get_course_lectures.php"
        params = {"course_id": course_id}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error fetching course lectures: {e}")
            return []
