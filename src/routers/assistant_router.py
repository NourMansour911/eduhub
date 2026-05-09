from fastapi import APIRouter, Depends

from helpers import get_logger
from schemas import SummarizeRequest, SummarizeResponse
from services.summarize import get_summarize_service, SummarizeService

logger = get_logger(__name__)

assistant_router = APIRouter(
	prefix="/assistant",
	tags=["Assistant"],
)


@assistant_router.post(
	"/summarize",
	summary="Summarize a lecture",
	description="Generate a summary for a lecture by lecture_id and requested length level (0,1,2).",
	response_model=SummarizeResponse,
)
async def summarize(
	payload: SummarizeRequest,
	service: SummarizeService = Depends(get_summarize_service),
) -> SummarizeResponse:
	output_text = await service.get_summary(payload.lecture_id, payload.length)
	return SummarizeResponse(summary=output_text)
