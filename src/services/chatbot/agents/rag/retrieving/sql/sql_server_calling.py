

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
        logger.info("[SqlServerCalling] GET course_details | url: %s | params: %s", url, params)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()["data"]
                logger.info("[SqlServerCalling] course_details OK | course_id: %s | keys: %s", course_id, list(data.keys()) if isinstance(data, dict) else f"list[{len(data)}]")
                return data
        except httpx.HTTPError as e:
            logger.error("[SqlServerCalling] course_details FAILED | course_id: %s | error: %s", course_id, e)
            raise e

    async def get_student_courses(self, student_id: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/get_student_courses.php"
        params = {"student_id": student_id}
        logger.info("[SqlServerCalling] GET student_courses | url: %s | params: %s", url, params)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()["data"]
                logger.info("[SqlServerCalling] student_courses OK | student_id: %s | count: %d", student_id, len(data))
                return data
        except httpx.HTTPError as e:
            logger.error("[SqlServerCalling] student_courses FAILED | student_id: %s | error: %s", student_id, e)
            raise e

    async def get_course_lectures(self, course_id: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/get_course_lectures.php"
        params = {"course_id": course_id}
        logger.info("[SqlServerCalling] GET course_lectures | url: %s | params: %s", url, params)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()["data"]
                logger.info("[SqlServerCalling] course_lectures OK | course_id: %s | count: %d", course_id, len(data))
                return data
        except httpx.HTTPError as e:
            logger.error("[SqlServerCalling] course_lectures FAILED | course_id: %s | error: %s", course_id, e)
            raise e
