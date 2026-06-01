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

	async def build_context(self, message: str) -> Dict[str, Any]:
		message = (message or "").strip()
		if not message:
			raise ValueError("message is required")

		return await self.rag_subgraph.ainvoke({"user_query": message})

	async def chat(self, payload: ChatRequest) -> ChatResponse:
		result = await self.build_context(payload.message)
		return ChatResponse(
			ai_response=json.dumps(result.get("plan", result), ensure_ascii=False, default=str)
		)


def get_chatbot_service(
	lc_openai_client: LCOpenAI = Depends(get_langchain_client),
	settings: Settings = Depends(get_settings),
) -> ChatbotService:
	return ChatbotService(lc_openai_client=lc_openai_client, settings=settings)


__all__ = ["ChatbotService", "get_chatbot_service"]