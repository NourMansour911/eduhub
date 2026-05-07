

from fastapi import Request
from azure.ai.documentintelligence import DocumentIntelligenceClient

from repositories import AnswerRepo, LectureRepo


def get_langchain_client(request: Request):
    return request.app.state.langchain_client


def get_answer_repo(request: Request) -> AnswerRepo:

    return request.app.state.answer_repo


def get_lecture_repo(request: Request) -> LectureRepo:

    return request.app.state.lecture_repo


def get_vdb_client(request: Request):

    return request.app.state.vdb_client


def get_embedding_client(request: Request):
    return request.app.state.embedding_client


def get_doc_intelligence_client(request: Request) -> DocumentIntelligenceClient:
    return request.app.state.doc_intelligence_client




