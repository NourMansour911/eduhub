import os
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


class MockRedisProvider:
    """No-op Redis stand-in for graph visualisation in LangGraph Studio."""

    async def get_collection(self, **_):
        return None

    async def save_collection(self, *_, **__):
        pass

    async def clear_session_collection(self, **_):
        pass

    def build_collection_key(self, **_) -> str:
        return "mock-key"

    async def connect(self):
        pass

    async def disconnect(self):
        pass

from core import get_settings
from integrations.llm import LCOpenAI, LLMFactory
from integrations.vector_db import VectorDBFactory
from motor.motor_asyncio import AsyncIOMotorClient
from repositories.lecture_repo import LectureRepo
from repositories.student_persona_repo import StudentPersonaRepo
from services.lectures.lecture_service import LectureService
from services.summarize.summarize_service import SummarizeService
from services.vdb_service.vectordb_service import VDBService
from services.chatbot.agents.rag.retrieving.vdb.search_service import SearchService
from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools
from services.chatbot.agents.rag.builder import build_rag_subgraph
from services.chatbot.builder import build_chatbot_graph
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

settings = get_settings()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = settings.APP_NAME

lc_openai_client = LCOpenAI(api_key=settings.OPENAI_API_KEY, api_url=settings.OPENAI_API_URL)

llm_provider_factory = LLMFactory()
embedding_client = llm_provider_factory.create(api_key="hf", provider=settings.EMBEDDING_BACKEND)
embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_MODEL_SIZE)

vdb_provider_factory = VectorDBFactory(settings)
vdb_client = vdb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
vdb_client.connect()
search_service = SearchService(
    vdb_client=vdb_client,
    embedding_client=embedding_client,
    settings=settings,
    langchain_client=lc_openai_client,
)
vdb_tools = VDBTools(search_service=search_service)

mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
mongo_db = mongo_client[settings.MONGO_DB_NAME]
lecture_repo = LectureRepo(mongo_db)

vdb_service = VDBService(vdb_client=vdb_client)
doc_intelligence_client = DocumentIntelligenceClient(
    endpoint=settings.AZURE_DOC_ENDPOINT,
    credential=AzureKeyCredential(settings.AZURE_DOC_KEY),
)
summary_llm = lc_openai_client.get_langchain_llm(
    model=settings.GENERATION_MODEL_ID,
    temperature=0.1,
    top_p=0.85,
)

lecture_service = LectureService(
    lecture_repo=lecture_repo,
    doc_intelligence_client=doc_intelligence_client,
    summary_llm=summary_llm,
    vdb_client=vdb_client,
    vdb_service=vdb_service,
)
summarize_service = SummarizeService(lecture_repo=lecture_repo, summary_llm=summary_llm)

mongodb_tools = MongoDBTools(
    lecture_service=lecture_service,
    summarize_service=summarize_service,
)

sql_tools = SQLTools(embedding_client=embedding_client)


chatbot_llm_map = {
    "orchestrator": lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID, temperature=0.0
    ),
    "answering": lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID, temperature=0.7
    ),
    "summary": lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID, temperature=0.1
    ),
    "persona": lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID, temperature=0.1
    ),
}


rag_subgraph = build_rag_subgraph(
    lc_openai_client=lc_openai_client,
    settings=settings,
    vdb_tools=vdb_tools,
    mongodb_tools=mongodb_tools,
    sql_tools=sql_tools,
    redis_provider=MockRedisProvider(),
)


graph = build_chatbot_graph(
    llm_map=chatbot_llm_map,
    rag_subgraph=rag_subgraph,
    redis_provider=MockRedisProvider(),
)
