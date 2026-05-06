from fastapi import APIRouter, Depends

from helpers import get_logger
from schemas import RefGradingRequest, RefGradingResponse, BatchGradingRequest, BatchGradingResponse
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
    "/grade-batch",
    summary="Grade multiple student answers",
    description="Grades multiple student answers against stored reference answers.",
    response_model=BatchGradingResponse,
)
async def grade_batch(
    payload: BatchGradingRequest,
    grading_service: SetScoreService = Depends(get_set_score_service),
) -> BatchGradingResponse:
    return await grading_service.batch_grade(payload)









