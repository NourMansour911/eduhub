

from fastapi import Request

from repositories import AnswerRepo


def get_langchain_client(request: Request):
    return request.app.state.langchain_client


def get_answer_repo(request: Request) -> AnswerRepo:

    return request.app.state.answer_repo


def get_vdb_client(request: Request):

    return request.app.state.vdb_client


def get_embedding_client(request: Request):
    return request.app.state.embedding_client


