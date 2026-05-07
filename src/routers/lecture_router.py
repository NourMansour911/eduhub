from fastapi import APIRouter, Depends

from helpers import get_logger
from schemas import (
    DeleteLectureResponse,
    LectureStoreRequest,
    LectureDeleteByIdRequest,
    LectureDeleteBySubjectRequest,
    LectureListResponse,
    LectureResponse,
)
from services import lecture_service

logger = get_logger(__name__)

lecture_route = APIRouter(
    prefix="/lectures",
    tags=["Lectures"],
)


@lecture_route.post(
    "",
    summary="Create lecture",
    description="Stores a lecture document with AnalyzeResult content.",
    response_model=LectureResponse,
)
async def store_lecture(
    payload: LectureStoreRequest,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> LectureResponse:
    return await service.store_lecture(payload)


@lecture_route.get(
    "/{lecture_id}",
    summary="Get lecture by lecture_id",
    description="Returns a lecture document using lecture_id.",
    response_model=LectureResponse,
)
async def get_lecture(
    lecture_id: str,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> LectureResponse:
    return await service.get_lecture(lecture_id)


@lecture_route.get(
    "/subject/{subject_id}",
    summary="List lectures by subject",
    description="Returns all lectures for a subject_id.",
    response_model=LectureListResponse,
)
async def get_lectures_by_subject(
    subject_id: str,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> LectureListResponse:
    return await service.get_lectures_by_subject(subject_id)


@lecture_route.delete(
    "/{lecture_id}",
    summary="Delete lecture by lecture_id",
    description="Deletes a lecture using lecture_id.",
    response_model=DeleteLectureResponse,
)
async def delete_lecture(
    lecture_id: str,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> DeleteLectureResponse:
    return await service.delete_lecture(LectureDeleteByIdRequest(lecture_id=lecture_id))


@lecture_route.delete(
    "/subject/{subject_id}",
    summary="Delete lectures by subject_id",
    description="Deletes all lectures for a subject_id.",
    response_model=DeleteLectureResponse,
)
async def delete_lectures_by_subject(
    subject_id: str,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> DeleteLectureResponse:
    return await service.delete_lectures_by_subject(LectureDeleteBySubjectRequest(subject_id=subject_id))
