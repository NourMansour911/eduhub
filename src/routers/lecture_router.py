from fastapi import APIRouter, Depends

from helpers import get_logger
from schemas import (
    DeleteLectureResponse,
    LectureStoreRequest,
    DeleteLectureByIdRequest,
    DeleteLectureBycourseIdRequest,
    LectureListResponse,
    LectureStoreResponse,
)
from models import LectureModel
from services.lectures import lecture_service
from orchestrators import LectureOrchestrator, get_lecture_orchestrator

logger = get_logger(__name__)

lecture_route = APIRouter(
    prefix="/lectures",
    tags=["Lectures"],
)


@lecture_route.post(
    "",
    summary="Store lecture",
    description="Stores a lecture document with Azure Document Intelligence AnalyzeResult content and generates summaries.",
)
async def store_lecture(
    payload: LectureStoreRequest,
    orchestrator: LectureOrchestrator = Depends(get_lecture_orchestrator),
) -> LectureStoreResponse:
    return await orchestrator.store_lecture_with_summaries(payload)


@lecture_route.get(
    "/{lecture_id}",
    summary="Get lecture by lecture_id",
    description="Returns a lecture document using lecture_id.",
    response_model=LectureModel,
)
async def get_lecture(
    lecture_id: str,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> LectureModel:
    return await service.get_lecture(lecture_id)


@lecture_route.get(
    "/course/{course_id}",
    summary="List lectures by course",
    description="Returns all lectures for a course_id.",
    response_model=LectureListResponse,
)
async def get_lectures_by_course(
    course_id: str,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> LectureListResponse:
    return await service.get_lectures_by_course(course_id)


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
    return await service.delete_lecture(DeleteLectureByIdRequest(lecture_id=lecture_id))


@lecture_route.delete(
    "/course/{course_id}",
    summary="Delete lectures by course_id",
    description="Deletes all lectures for a course_id.",
    response_model=DeleteLectureResponse,
)
async def delete_lectures_by_course(
    course_id: str,
    service: lecture_service.LectureService = Depends(lecture_service.get_lecture_service),
) -> DeleteLectureResponse:
    return await service.delete_lectures_by_course(DeleteLectureBycourseIdRequest(course_id=course_id))
