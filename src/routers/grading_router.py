from fastapi import APIRouter, Depends

from helpers import get_logger
from orchestrator import GradingOrchestrator, get_grading_orchestrator
from schemas import GradingRequest, GradingResponse, RefGradingRequest, RefGradingResponse

logger = get_logger(__name__)

grading_route = APIRouter(
    prefix="/essay",
    tags=["essay grading"],
)


@grading_route.post(
    "/reference",
    summary="Set reference answer",
    description="Accepts the reference answer for later grading.",
    response_model=RefGradingResponse,
)
async def set_reference_answer(
    payload: RefGradingRequest,
    orchestrator: GradingOrchestrator = Depends(get_grading_orchestrator),
) -> RefGradingResponse:
    return await orchestrator.set_reference_answer(payload)


@grading_route.post(
    "/grade",
    summary="Grade student answer",
    description="Grades a student answer against the stored reference answer.",
    response_model=GradingResponse,
)
async def grade_answer(
    payload: GradingRequest,
    orchestrator: GradingOrchestrator = Depends(get_grading_orchestrator),
) -> GradingResponse:
    return await orchestrator.grade_answer(payload)




