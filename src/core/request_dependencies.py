from typing import Optional, TYPE_CHECKING

from fastapi import Request
from azure.ai.documentintelligence import DocumentIntelligenceClient

from repositories.answer_repo import AnswerRepo
from repositories.lecture_repo import LectureRepo
from repositories.evaluation_repo import EvaluationRepo
from repositories.student_persona_repo import StudentPersonaRepo

if TYPE_CHECKING:
    from integrations.redis_provider import RedisProvider
    from services.chatbot.chatbot_service import ChatbotService
    from services.lectures.lecture_service import LectureService
    from services.summarize.summarize_service import SummarizeService
    from services.vdb_service.vectordb_service import VDBService
    from services.session.session_service import SessionService
    from services.grading.set_reference import SetReferenceService
    from services.grading.set_score import SetScoreService
    from orchestrators.lecture_orchestrator import LectureOrchestrator



def get_langchain_client(request: Request):

    return request.app.state.langchain_client


def get_answer_repo(request: Request) -> AnswerRepo:

    return request.app.state.answer_repo


def get_evaluation_repo(request: Request) -> EvaluationRepo:
    return request.app.state.evaluation_repo


def get_lecture_repo(request: Request) -> LectureRepo:

    return request.app.state.lecture_repo


def get_student_persona_repo(request: Request) -> StudentPersonaRepo:
    return request.app.state.student_persona_repo


def get_vdb_client(request: Request):

    return request.app.state.vdb_client


def get_embedding_client(request: Request):
    return request.app.state.embedding_client


def get_redis_provider(request: Request) -> "RedisProvider":
    return request.app.state.redis_provider


def get_doc_intelligence_client(request: Request) -> DocumentIntelligenceClient:
    return request.app.state.doc_intelligence_client


def get_chatbot_service(request: Request) -> "ChatbotService":
    return request.app.state.chatbot_service


def get_lecture_service(request: Request) -> "LectureService":
    return request.app.state.lecture_service


def get_summarize_service(request: Request) -> "SummarizeService":
    return request.app.state.summarize_service


def get_vdb_service(request: Request) -> "VDBService":
    return request.app.state.vdb_service


def get_session_service(request: Request) -> "SessionService":
    return request.app.state.session_service


def get_set_reference_service(request: Request) -> "SetReferenceService":
    return request.app.state.set_reference_service


def get_set_score_service(request: Request) -> "SetScoreService":
    return request.app.state.set_score_service


def get_lecture_orchestrator(request: Request) -> "LectureOrchestrator":
    return request.app.state.lecture_orchestrator





