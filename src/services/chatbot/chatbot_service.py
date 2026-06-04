
from typing import Any, Dict

from fastapi import Depends

from core import Settings, get_settings
from core.request_dependencies import get_langchain_client
from integrations.llm import LCOpenAI
from schemas import ChatRequest, ChatResponse

from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools, get_vdb_tools
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools, get_mongodb_tools
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools, get_sql_tools

from .agents.rag import build_rag_subgraph


class ChatbotService:
    def __init__(
        self,
        lc_openai_client: LCOpenAI,
        settings: Settings,
        vdb_tools: VDBTools,
        mongodb_tools: MongoDBTools,
        sql_tools: SQLTools,
    ) -> None:
        self.rag_subgraph = build_rag_subgraph(
            lc_openai_client=lc_openai_client,
            settings=settings,
            vdb_tools=vdb_tools,
            mongodb_tools=mongodb_tools,
            sql_tools=sql_tools,
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
    vdb_tools: VDBTools = Depends(get_vdb_tools),
    mongodb_tools: MongoDBTools = Depends(get_mongodb_tools),
    sql_tools: SQLTools = Depends(get_sql_tools),
) -> ChatbotService:
    return ChatbotService(
        lc_openai_client=lc_openai_client,
        settings=settings,
        vdb_tools=vdb_tools,
        mongodb_tools=mongodb_tools,
        sql_tools=sql_tools,
    )


