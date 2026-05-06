from typing import Any

from bson import ObjectId
from fastapi import Depends

from core.request_dependencies import get_lecture_repo
from models import LectureModel
from repositories import LectureRepo
from schemas import (
    DeleteLectureResponse,
    LectureCreateRequest,
    LectureListResponse,
    LectureResponse,
)
from services.service_exceptions import NotFoundError, ValidationError


def _serialize_content(content: Any) -> Any:
    if hasattr(content, "as_dict"):
        return content.as_dict()
    return content


class LectureService:
    def __init__(self, lecture_repo: LectureRepo):
        self.lecture_repo = lecture_repo

    async def create_lecture(self, payload: LectureCreateRequest) -> LectureResponse:
        if not payload.lecture_id.strip():
            raise ValidationError(details={"field": "lecture_id", "message": "lecture_id is required"})
        if not payload.subject_id.strip():
            raise ValidationError(details={"field": "subject_id", "message": "subject_id is required"})
        if not payload.subject_name.strip():
            raise ValidationError(details={"field": "subject_name", "message": "subject_name is required"})

        lecture = LectureModel(
            lecture_id=payload.lecture_id.strip(),
            subject_id=payload.subject_id.strip(),
            subject_name=payload.subject_name.strip(),
            content=payload.content,
            order=payload.order,
        )
        inserted_id = await self.lecture_repo.add_lecture(lecture)

        return LectureResponse(
            _id=str(inserted_id),
            lecture_id=lecture.lecture_id,
            subject_id=lecture.subject_id,
            subject_name=lecture.subject_name,
            content=_serialize_content(lecture.content),
            order=lecture.order,
        )

    async def get_lecture(self, lecture_id: str) -> LectureResponse:
        lecture = await self.lecture_repo.get_lecture_by_lecture_id(lecture_id)
        if not lecture:
            raise NotFoundError(details={"lecture_id": lecture_id})

        return LectureResponse(
            _id=str(lecture.iid) if lecture.iid else None,
            lecture_id=lecture.lecture_id,
            subject_id=lecture.subject_id,
            subject_name=lecture.subject_name,
            content=_serialize_content(lecture.content),
            order=lecture.order,
        )

    async def get_lectures_by_subject(self, subject_id: str) -> LectureListResponse:
        lectures = await self.lecture_repo.get_lectures_by_subject(subject_id)
        items = [
            LectureResponse(
                _id=str(lecture.iid) if lecture.iid else None,
                lecture_id=lecture.lecture_id,
                subject_id=lecture.subject_id,
                subject_name=lecture.subject_name,
                content=_serialize_content(lecture.content),
                order=lecture.order,
            )
            for lecture in lectures
        ]
        return LectureListResponse(items=items)

    async def delete_lecture(self, lecture_id: str) -> DeleteLectureResponse:
        deleted_count = await self.lecture_repo.delete_by_lecture_id(lecture_id)
        if deleted_count == 0:
            raise NotFoundError(details={"lecture_id": lecture_id})
        return DeleteLectureResponse(lecture_id=lecture_id, deleted_count=deleted_count)

    async def delete_lectures_by_subject(self, subject_id: str) -> DeleteLectureResponse:
        deleted_count = await self.lecture_repo.delete_by_subject_id(subject_id)
        if deleted_count == 0:
            raise NotFoundError(details={"subject_id": subject_id})
        return DeleteLectureResponse(subject_id=subject_id, deleted_count=deleted_count)


def get_lecture_service(
    lecture_repo: LectureRepo = Depends(get_lecture_repo),
) -> LectureService:
    return LectureService(lecture_repo=lecture_repo)
