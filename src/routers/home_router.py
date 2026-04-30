from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from helpers import get_logger
from core import Settings, get_settings

logger = get_logger(__name__)

home_route = APIRouter(
    prefix="",
    tags=["Welcome"],
)

@home_route.get(
    "/",
    summary="Service status",
    description="Returns the application name, version, status, and current timestamp.",
    response_description="Basic runtime information for the service."
)
async def home(settings: Settings = Depends(get_settings)):
    logger.info("Home endpoint called")

    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }