from fastapi import APIRouter, Depends, Path

from helpers.logger import get_logger
from schemas import SummarizeRequest, SummarizeResponse
from services.summarize.summarize_service import  SummarizeService
from schemas import ChatRequest
from schemas.assistant_schema import ChatResponse, DeletePersonaResponse
from services.chatbot.chatbot_service import ChatbotService
from core.request_dependencies import (
	get_chatbot_service,
	get_summarize_service,
)
from services.service_exceptions import NotFoundError, ProcessingError

logger = get_logger(__name__)

assistant_route = APIRouter(
	prefix="/assistant",
	tags=["Assistant"],
)



@assistant_route.post(
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



@assistant_route.post(
    "/chat/{user_id}/{session_id}",
    summary="Chat with project files",
    description="Starts a retrieval-augmented chat session over the selected project's files.",
    response_description="Chat answer payload.",
    response_model=ChatResponse
)
async def chat(
    chat_request: ChatRequest,
    session_id: str = Path(..., description="Session identifier used for memory and trace metadata."),
    user_id: str = Path(..., description="User identifier used for memory and trace metadata."),
	service: ChatbotService = Depends(get_chatbot_service),
):
	return await service.chat(chat_request, user_id, session_id)


@assistant_route.delete(
    "/persona/{user_id}",
    summary="Delete student persona",
    description=(
        "Deletes the stored persona for a given user from the database. "
        "This operation is blocked if the user has any active session — "
        "you must end all sessions first before deleting the persona."
    ),
    response_model=DeletePersonaResponse,
)
async def delete_persona(
    user_id: str = Path(..., description="User identifier whose persona will be deleted."),
    chatbot_service: ChatbotService = Depends(get_chatbot_service),
):
    return await chatbot_service.delete_student_persona(user_id)


