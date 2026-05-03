from fastapi import APIRouter, Depends

from helpers import get_logger
from schemas import GradingRequest, GradingResponse, RefGradingRequest, RefGradingResponse
from services.grading import SetReferenceService, get_set_reference_service

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






