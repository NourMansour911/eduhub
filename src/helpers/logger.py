import logging
from logging.handlers import RotatingFileHandler
import os
import json
from rich.logging import RichHandler

BASE_STORAGE_PATH = os.getenv("STORAGE_PATH")
if not BASE_STORAGE_PATH:
    BASE_STORAGE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
elif not os.path.isabs(BASE_STORAGE_PATH):
    src_dir = os.path.dirname(os.path.dirname(__file__))
    BASE_STORAGE_PATH = os.path.abspath(os.path.join(src_dir, BASE_STORAGE_PATH))

LOG_DIR = os.path.join(BASE_STORAGE_PATH, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")
CHATBOT_LOG_FILE = os.path.join(LOG_DIR, "chatbot.log")
INTEGRATIONS_LOG_FILE = os.path.join(LOG_DIR, "integrations.log")


class PrettyFormatter(logging.Formatter):
    """Custom formatter that automatically pretty-prints JSON strings and dict/list objects."""
    def format(self, record):
        # Store original message to avoid mutating it permanently for other handlers
        orig_msg = record.msg
        
        # Check if message is a string that looks like JSON
        if isinstance(record.msg, str):
            stripped = record.msg.strip()
            if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                try:
                    parsed = json.loads(record.msg)
                    record.msg = json.dumps(parsed, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        # If the message is already a dictionary or list
        elif isinstance(record.msg, (dict, list)):
            try:
                record.msg = json.dumps(record.msg, indent=2, ensure_ascii=False)
            except Exception:
                pass
        
        # Also handle arguments if they contain dict/list/json
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, (dict, list)):
                    try:
                        new_args.append(json.dumps(arg, indent=2, ensure_ascii=False))
                    except Exception:
                        new_args.append(arg)
                elif isinstance(arg, str):
                    stripped = arg.strip()
                    if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                        try:
                            parsed = json.loads(arg)
                            new_args.append(json.dumps(parsed, indent=2, ensure_ascii=False))
                        except Exception:
                            new_args.append(arg)
                    else:
                        new_args.append(arg)
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)

        result = super().format(record)
        
        # Restore original message and args
        record.msg = orig_msg
        return result


def _setup_logger(logger_name: str, file_path: str, console_level: int = logging.INFO, file_level: int = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)  # Capture all logs at the logger level

    # Clear existing handlers to prevent duplicates
    logger.handlers.clear()
    
    # Console handler
    ch = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=True,
        markup=False, # Avoid parsing bracket symbols as console markup
    )
    ch.setLevel(console_level)
    ch.setFormatter(PrettyFormatter("%(message)s"))

    # File handler with rotation
    fh = RotatingFileHandler(
        file_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(file_level)
    fh.setFormatter(PrettyFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))

    logger.addHandler(ch)
    logger.addHandler(fh)

    return logger


def get_logger(name: str) -> logging.Logger:
    # General logger for the application (writes to app.log, console level is INFO)
    return _setup_logger(name, LOG_FILE, console_level=logging.INFO)


def get_chatbot_logger(name: str) -> logging.Logger:
    # Chatbot logger (writes to chatbot.log, console level is WARNING to prevent clutter)
    return _setup_logger(f"chatbot.{name}", CHATBOT_LOG_FILE, console_level=logging.INFO)


def get_integrations_logger(name: str) -> logging.Logger:
    # Integrations logger (writes to integrations.log, console level is WARNING to prevent clutter)
    return _setup_logger(f"integrations.{name}", INTEGRATIONS_LOG_FILE, console_level=logging.INFO)