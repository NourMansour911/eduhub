from fastapi import APIRouter, Depends

from helpers import get_logger
from schemas import GradingRequest, GradingResponse, RefGradingRequest, RefGradingResponse
from services.grading import (
    SetReferenceService,
    SetScoreService,
    get_set_reference_service,
    get_set_score_service,
)

logger = get_logger(__name__)

grading_route = APIRouter(
    prefix="/essay",
    tags=["essay grading"],
)


@grading_route.post(
    "/set-reference",
    summary="Set reference answer",
    description="Accepts the reference answer for later grading.",
    response_model=RefGradingResponse,
)
async def set_reference_answer(
    payload: RefGradingRequest,
    store_ref_service: SetReferenceService = Depends(get_set_reference_service),
) -> RefGradingResponse:
    return await store_ref_service.store_reference(payload)


@grading_route.post(
    "/grade",
    summary="Grade student answer",
    description="Grades the student answer against the stored reference answer.",
    response_model=GradingResponse,
)
async def grade(
    payload: GradingRequest,
    grading_service: SetScoreService = Depends(get_set_score_service),
) -> GradingResponse:
    return await grading_service.set_score(payload)









