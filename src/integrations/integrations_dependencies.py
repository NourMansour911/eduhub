from fastapi import Request
from .llm import LLMFactory, LCOpenAI
from .vector_db import VectorDBFactory

def get_vdb_client(request: Request) -> VectorDBFactory:
    return request.app.state.vdb_client


def get_embedding_client(request: Request) -> LLMFactory:
    return request.app.state.embedding_client

def get_langchain_client(request: Request) -> LCOpenAI:
    return request.app.state.langchain_client