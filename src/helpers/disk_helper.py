import os

from helpers.logger import get_logger
from core.settings import get_settings

logger = get_logger(__name__)

settings = get_settings()


def _base_storage_path(directory: str = "files") -> str:
    return os.path.join(settings.STORAGE_PATH, directory)


def get_project_path(tenant_id: str, project_id: str, stage: str = "raw") -> str:
    allowed_stages = ["raw", "normalized", "temp", "all"]

    if stage not in allowed_stages:
        raise ValueError(f"Unknown stage: {stage}")

    base_path = _base_storage_path()

    if stage == "all":
        return os.path.join(base_path, tenant_id, project_id)

    project_path = os.path.join(base_path, tenant_id, project_id, stage)
    os.makedirs(project_path, exist_ok=True)

    logger.debug(f"Project {stage} path: {project_path}")
    return project_path


def get_tenant_path(tenant_id: str) -> str:
    path = os.path.join(_base_storage_path(), tenant_id)
    os.makedirs(path, exist_ok=True)
    return path