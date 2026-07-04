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
    
    def format(self, record):
        orig_msg = record.msg
        orig_args = record.args
        
        if isinstance(record.msg, str):
            stripped = record.msg.strip()
            if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                try:
                    parsed = json.loads(record.msg)
                    record.msg = json.dumps(parsed, indent=2, ensure_ascii=False)
                except Exception:
                    pass
        elif isinstance(record.msg, (dict, list)):
            try:
                record.msg = json.dumps(record.msg, indent=2, ensure_ascii=False)
            except Exception:
                pass
        
        if record.args:
            if isinstance(record.args, dict):
                if isinstance(record.msg, str) and '%(' in record.msg:
                    new_args = {}
                    for k, v in record.args.items():
                        if isinstance(v, (dict, list)):
                            try:
                                new_args[k] = json.dumps(v, indent=2, ensure_ascii=False)
                            except Exception:
                                new_args[k] = v
                        elif isinstance(v, str):
                            stripped = v.strip()
                            if (stripped.startswith('{') and stripped.endswith('}')) or (stripped.startswith('[') and stripped.endswith(']')):
                                try:
                                    parsed = json.loads(v)
                                    new_args[k] = json.dumps(parsed, indent=2, ensure_ascii=False)
                                except Exception:
                                    new_args[k] = v
                            else:
                                new_args[k] = v
                        else:
                            new_args[k] = v
                    record.args = new_args
                else:
                    try:
                        pretty_dict = json.dumps(record.args, indent=2, ensure_ascii=False)
                        record.args = (pretty_dict,)
                    except Exception:
                        record.args = (record.args,)
            else:
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

        try:
            result = super().format(record)
        finally:
            record.msg = orig_msg
            record.args = orig_args
        return result



def _setup_logger(logger_name: str, file_path: str, console_level: int = logging.INFO, file_level: int = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)  

    logger.handlers.clear()
    
    ch = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=True,
        markup=False, 
    )
    ch.setLevel(console_level)
    ch.setFormatter(PrettyFormatter("%(message)s"))

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
    return _setup_logger(name, LOG_FILE, console_level=logging.INFO)


def get_chatbot_logger(name: str) -> logging.Logger:
    return _setup_logger(f"chatbot.{name}", CHATBOT_LOG_FILE, console_level=logging.INFO)


def get_integrations_logger(name: str) -> logging.Logger:
    return _setup_logger(f"integrations.{name}", INTEGRATIONS_LOG_FILE, console_level=logging.INFO)