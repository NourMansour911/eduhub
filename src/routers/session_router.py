from fastapi import APIRouter, Depends, Path

from helpers import get_logger
from schemas.session_schema import SessionEndResponse, SessionRequest, SessionStartResponse
from services.session import SessionService, get_session_service

logger = get_logger(__name__)

session_route = APIRouter(
    prefix="/session",
    tags=["Sessions"],
)


@session_route.post(
    "/start/{user_id}/{session_id}",
    summary="Start session",
    description="Starts a session for a user and session identifier.",
    response_description="Session start payload.",
    response_model=SessionStartResponse,
)
async def start_session(
    user_id: str = Path(..., description="User identifier for the session."),
    session_id: str = Path(..., description="Session identifier."),
    session_service: SessionService = Depends(get_session_service),
):
    logger.info("Starting session user_id=%s session_id=%s", user_id, session_id)

    return await session_service.start_session(
        request=SessionRequest(user_id=user_id, session_id=session_id),
    )


@session_route.post(
    "/end/{user_id}/{session_id}",
    summary="End session",
    description="Ends a session for a user and session identifier.",
    response_description="Session end payload.",
    response_model=SessionEndResponse,
)
async def end_session(
    user_id: str = Path(..., description="User identifier for the session."),
    session_id: str = Path(..., description="Session identifier."),
    session_service: SessionService = Depends(get_session_service),
):
    logger.info("Ending session user_id=%s session_id=%s", user_id, session_id)

    return await session_service.end_session(
        request=SessionRequest(user_id=user_id, session_id=session_id),
    )

