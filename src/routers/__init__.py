# Auto-generated __init__.py

from . import assistant_router
from .assistant_router import chat
from .assistant_router import summarize
from . import grading_router
from .grading_router import grade_batch
from .grading_router import set_reference_answer
from . import home_router
from .home_router import home
from . import lecture_router
from .lecture_router import delete_lecture
from .lecture_router import delete_lectures_by_course
from .lecture_router import get_lecture
from .lecture_router import get_lectures_by_course
from .lecture_router import store_lecture
from . import session_router
from .session_router import end_session
from .session_router import start_session
from . import vectordb_router
from .vectordb_router import delete_collection
from .vectordb_router import get_collection_chunks
from .vectordb_router import get_collection_info
from .vectordb_router import search_collection

__all__ = [
    "assistant_router",
    "grading_router",
    "home_router",
    "lecture_router",
    "session_router",
    "vectordb_router",
    "chat",
    "delete_collection",
    "delete_lecture",
    "delete_lectures_by_course",
    "end_session",
    "get_collection_chunks",
    "get_collection_info",
    "get_lecture",
    "get_lectures_by_course",
    "grade_batch",
    "home",
    "search_collection",
    "set_reference_answer",
    "start_session",
    "store_lecture",
    "summarize",
]
