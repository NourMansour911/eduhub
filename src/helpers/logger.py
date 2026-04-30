import logging
from logging.handlers import RotatingFileHandler
import os

BASE_STORAGE_PATH = os.getenv(
    "STORAGE_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage"),
)
LOG_DIR = os.path.join(BASE_STORAGE_PATH, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "logs.log")

def get_logger(name: str, level: str="error"):

    logger = logging.getLogger(name)
    try:
        match level.lower():
            case "debug":
                logger.setLevel(logging.DEBUG)
            case "info":
                logger.setLevel(logging.INFO)
            case "warning":
                logger.setLevel(logging.WARNING)
            case "error":
                logger.setLevel(logging.ERROR)
            case "critical":
                logger.setLevel(logging.CRITICAL)
            case _:
                logger.setLevel(logging.ERROR)
    except Exception:
        logger.setLevel(logging.ERROR)

    if not logger.hasHandlers():
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

        # File handler with rotation
        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=5_000_000, backupCount=5
        )
        fh.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

        logger.addHandler(ch)
        logger.addHandler(fh)

    return logger