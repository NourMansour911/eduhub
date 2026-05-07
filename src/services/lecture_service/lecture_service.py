from typing import Any

from fastapi import Depends
from pymongo.errors import DuplicateKeyError

from core.request_dependencies import get_lecture_repo
from models import LectureModel
from repositories import LectureRepo
from schemas import (
    DeleteLectureResponse,
    LectureStoreRequest,
    LectureDeleteByIdRequest,
    LectureDeleteBySubjectRequest,
    LectureListResponse,
    LectureResponse,
)

from .lecture_exceptions import (
    LectureConflictError,
    LectureNotFoundError,
    LectureServiceException,
)


def _serialize_content(content: Any) -> Any:
    if hasattr(content, "as_dict"):
        return content.as_dict()
    return content


class LectureService:
    def __init__(self, lecture_repo: LectureRepo):
        self.lecture_repo = lecture_repo

    async def store_lecture(self, payload: LectureStoreRequest) -> LectureResponse:
        lecture = LectureModel(
            lecture_id=payload.lecture_id,
            lecture_name=payload.lecture_name,
            subject_id=payload.subject_id,
            subject_name=payload.subject_name,
            content=payload.content,
            order=payload.order,
        )
        try:
            inserted_id = await self.lecture_repo.add_lecture(lecture)
        except DuplicateKeyError as exc:
            raise LectureConflictError(details={"lecture_id": lecture.lecture_id, "error": str(exc)})
        except Exception as exc:
            raise LectureServiceException(details={"operation": "store_lecture", "error": str(exc)})

        return LectureResponse(
            _id=str(inserted_id),
            lecture_id=lecture.lecture_id,
            lecture_name=lecture.lecture_name,
            subject_id=lecture.subject_id,
            subject_name=lecture.subject_name,
            content=_serialize_content(lecture.content),
            order=lecture.order,
        )

    async def get_lecture(self, lecture_id: str) -> LectureResponse:
        try:
            lecture = await self.lecture_repo.get_lecture_by_lecture_id(lecture_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "get_lecture", "error": str(exc)})
        if not lecture:
            raise LectureNotFoundError(details={"lecture_id": lecture_id})

        return LectureResponse(
            _id=str(lecture.iid) if lecture.iid else None,
            lecture_id=lecture.lecture_id,
            lecture_name=lecture.lecture_name,
            subject_id=lecture.subject_id,
            subject_name=lecture.subject_name,
            content=_serialize_content(lecture.content),
            order=lecture.order,
        )

    async def get_lectures_by_subject(self, subject_id: str) -> LectureListResponse:
        try:
            lectures = await self.lecture_repo.get_lectures_by_subject(subject_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "get_lectures_by_subject", "error": str(exc)})
        items = [
            LectureResponse(
                _id=str(lecture.iid) if lecture.iid else None,
                lecture_id=lecture.lecture_id,
                lecture_name=lecture.lecture_name,
                subject_id=lecture.subject_id,
                subject_name=lecture.subject_name,
                content=_serialize_content(lecture.content),
                order=lecture.order,
            )
            for lecture in lectures
        ]
        return LectureListResponse(items=items)

    async def delete_lecture(self, payload: LectureDeleteByIdRequest) -> DeleteLectureResponse:
        try:
            deleted_count = await self.lecture_repo.delete_by_lecture_id(payload.lecture_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "delete_lecture", "error": str(exc)})
        if deleted_count == 0:
            raise LectureNotFoundError(details={"lecture_id": payload.lecture_id})
        return DeleteLectureResponse(lecture_id=payload.lecture_id, deleted_count=deleted_count)

    async def delete_lectures_by_subject(self, payload: LectureDeleteBySubjectRequest) -> DeleteLectureResponse:
        try:
            deleted_count = await self.lecture_repo.delete_by_subject_id(payload.subject_id)
        except Exception as exc:
            raise LectureServiceException(details={"operation": "delete_lectures_by_subject", "error": str(exc)})
        if deleted_count == 0:
            raise LectureNotFoundError(details={"subject_id": payload.subject_id})
        return DeleteLectureResponse(subject_id=payload.subject_id, deleted_count=deleted_count)


def get_lecture_service(
    lecture_repo: LectureRepo = Depends(get_lecture_repo),
) -> LectureService:
    return LectureService(lecture_repo=lecture_repo)