from fastapi import APIRouter, Path
from datetime import datetime, timezone
from helpers import get_logger

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
)
async def start_session(
    user_id: str = Path(..., description="User identifier for the session."),
    session_id: str = Path(..., description="Session identifier."),
):
    logger.info("Starting session user_id=%s session_id=%s", user_id, session_id)

    return {
        "action": "start",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@session_route.post(
    "/end/{user_id}/{session_id}",
    summary="End session",
    description="Ends a session for a user and session identifier.",
    response_description="Session end payload.",
)
async def end_session(
    user_id: str = Path(..., description="User identifier for the session."),
    session_id: str = Path(..., description="Session identifier."),
):
    logger.info("Ending session user_id=%s session_id=%s", user_id, session_id)

    return {
        "action": "end",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

