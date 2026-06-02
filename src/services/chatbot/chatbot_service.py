from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import Depends

from core import Settings, get_settings
from core.request_dependencies import get_langchain_client
from integrations.llm import LCOpenAI
from schemas import ChatRequest, ChatResponse

from .agents.rag import build_rag_subgraph


class ChatbotService:
    def __init__(self, lc_openai_client: LCOpenAI, settings: Settings) -> None:
        self.rag_subgraph = build_rag_subgraph(
            lc_openai_client=lc_openai_client,
            settings=settings,
        )

    async def build_context(self, message: str, student_id: str) -> Dict[str, Any]:
        message = (message or "").strip()
        if not message:
            raise ValueError("message is required")

        student_id = (student_id or "").strip()
        if not student_id:
            raise ValueError("student_id is required")

        return await self.rag_subgraph.ainvoke(
            {"user_query": message, "student_id": student_id}
        )

    async def chat(self, payload: ChatRequest, student_id: str) -> ChatResponse:
        result = await self.build_context(payload.message, student_id)
        return ChatResponse(
            ai_response=result
        )


def get_chatbot_service(
    lc_openai_client: LCOpenAI = Depends(get_langchain_client),
    settings: Settings = Depends(get_settings),
) -> ChatbotService:
    return ChatbotService(lc_openai_client=lc_openai_client, settings=settings)


