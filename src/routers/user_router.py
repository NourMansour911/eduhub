from fastapi import APIRouter, Depends, Path

from helpers.logger import get_logger
from schemas.session_schema import DeleteUserSessionsResponse
from schemas.assistant_schema import DeletePersonaResponse
from services.session.session_service import SessionService
from services.chatbot.chatbot_service import ChatbotService
from core.request_dependencies import get_session_service, get_chatbot_service

logger = get_logger(__name__)

user_route = APIRouter(
    prefix="/user/{user_id}",
    tags=["User"],
)


@user_route.delete(
    "/sessions",
    summary="Delete all sessions for a user",
    description=(
        "Deletes all archived session vectors for a user from the vector database. "
        "Blocked if the user has any active session."
    ),
    response_model=DeleteUserSessionsResponse,
)
async def delete_user_sessions(
    user_id: str = Path(..., description="User identifier whose sessions will be deleted."),
    session_service: SessionService = Depends(get_session_service),
):
    await session_service.delete_user_sessions(user_id)
    return DeleteUserSessionsResponse(
        user_id=user_id,
        deleted=True,
        message=f"All session vectors for user '{user_id}' have been successfully deleted from the vector database."
    )


@user_route.delete(
    "/persona",
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
