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
from .lecture_router import delete_lectures_by_subject
from .lecture_router import get_lecture
from .lecture_router import get_lectures_by_subject
from .lecture_router import store_lecture
from . import vectordb_router
from .vectordb_router import delete_collection
from .vectordb_router import get_collection_chunks
from .vectordb_router import get_collection_info

__all__ = [
    "assistant_router",
    "grading_router",
    "home_router",
    "lecture_router",
    "vectordb_router",
    "chat",
    "delete_collection",
    "delete_lecture",
    "delete_lectures_by_subject",
    "get_collection_chunks",
    "get_collection_info",
    "get_lecture",
    "get_lectures_by_subject",
    "grade_batch",
    "home",
    "set_reference_answer",
    "store_lecture",
    "summarize",
]
