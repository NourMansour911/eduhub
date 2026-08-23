import os
import uvicorn
from core import get_settings
settings = get_settings()
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = settings.APP_NAME

if "SSL_CERT_FILE" in os.environ and not os.path.exists(os.environ["SSL_CERT_FILE"]):
    del os.environ["SSL_CERT_FILE"]

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from core import app_exception_handler
from core.app_exceptions import AppException
from contextlib import asynccontextmanager
from helpers.logger import get_logger
from repositories.answer_repo import AnswerRepo
from repositories.lecture_repo import LectureRepo
from repositories.evaluation_repo import EvaluationRepo
from repositories.student_persona_repo import StudentPersonaRepo
from repositories.mongo_bootstrap import init_mongo_resources
from routers import grading_router, home_router, lecture_router, session_router, vectordb_router, assistant_router, user_router
from integrations.redis_provider import RedisProvider
from integrations.vector_db import VectorDBFactory
from integrations.llm import LLMFactory,LCOpenAI

# Service & orchestrator imports
from services.vdb_service.vectordb_service import VDBService
from services.lectures.lecture_service import LectureService
from services.summarize.summarize_service import SummarizeService
from services.session.session_service import SessionService
from services.grading.set_reference import SetReferenceService
from services.grading.set_score import SetScoreService
from orchestrators.lecture_orchestrator import LectureOrchestrator
from services.chatbot.chatbot_service import ChatbotService

logger = get_logger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
  # Exception handler
  app.add_exception_handler(AppException, app_exception_handler)
  
   # VectorDB client
  vdb_provider_factory = VectorDBFactory(settings)
  app.state.vdb_client = vdb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
  app.state.vdb_client.connect()
  collections = await app.state.vdb_client.list_all_collections()
  logger.info(f"VectorDB client loaded successfully")
  logger.info(f"VectorDB Collections: {collections}")
  
  
  
  # LLM clients
  ## Embedding client
  llm_provider_factory = LLMFactory()
  app.state.embedding_client = llm_provider_factory.create(api_key="hf",provider=settings.EMBEDDING_BACKEND)
  app.state.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_MODEL_SIZE)
  logger.info("Embedding client loaded successfully")
  
  ## LangChain client
  app.state.langchain_client = LCOpenAI(api_key=settings.OPENAI_API_KEY,api_url=settings.OPENAI_API_URL)
  logger.info("LangChain client loaded successfully")

  # Mongo client
  app.state.mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
  app.state.mongo_db = app.state.mongo_client[settings.MONGO_DB_NAME]
  mongo_repos = await init_mongo_resources(
    app.state.mongo_db,
    [AnswerRepo, LectureRepo, EvaluationRepo, StudentPersonaRepo],
  )
  app.state.answer_repo = mongo_repos["AnswerRepo"]
  app.state.lecture_repo = mongo_repos["LectureRepo"]
  app.state.evaluation_repo = mongo_repos["EvaluationRepo"]
  app.state.student_persona_repo = mongo_repos["StudentPersonaRepo"]
  logger.info("Mongo repositories loaded successfully")

  # Redis client
  app.state.redis_provider = RedisProvider(settings.REDIS_URL)
  await app.state.redis_provider.connect()
  logger.info("Redis provider loaded successfully")

  # Azure Document Intelligence client
  app.state.doc_intelligence_client = DocumentIntelligenceClient(
    endpoint=settings.AZURE_DOC_ENDPOINT,
    credential=AzureKeyCredential(settings.AZURE_DOC_KEY),
  )
  logger.info("Azure Document Intelligence client loaded successfully")

  # Instantiate all main services and store them in app.state
  
  app.state.vdb_service = VDBService(vdb_client=app.state.vdb_client)

  summary_llm = app.state.langchain_client.get_langchain_llm(
      model=settings.GENERATION_MODEL_ID,
      temperature=0.1,
      top_p=0.85,
  )
  app.state.lecture_service = LectureService(
      lecture_repo=app.state.lecture_repo,
      doc_intelligence_client=app.state.doc_intelligence_client,
      summary_llm=summary_llm,
      vdb_client=app.state.vdb_client,
      vdb_service=app.state.vdb_service,
  )

  app.state.summarize_service = SummarizeService(
      lecture_repo=app.state.lecture_repo,
      summary_llm=summary_llm,
  )

  app.state.session_service = SessionService(
      redis_provider=app.state.redis_provider,
      embedding_client=app.state.embedding_client,
      vdb_service=app.state.vdb_service,
      student_persona_repo=app.state.student_persona_repo,
  )

  app.state.set_reference_service = SetReferenceService(
      answer_repo=app.state.answer_repo,
  )

  app.state.set_score_service = SetScoreService(
      answer_repo=app.state.answer_repo,
      settings=settings,
      lc_openai_client=app.state.langchain_client,
  )

  app.state.lecture_orchestrator = LectureOrchestrator(
      lecture_service=app.state.lecture_service,
      summarize_service=app.state.summarize_service,
      vdb_service=app.state.vdb_service,
      embedding_client=app.state.embedding_client,
  )

  app.state.chatbot_service = ChatbotService(
      lc_openai_client=app.state.langchain_client,
      settings=settings,
      vdb_client=app.state.vdb_client,
      embedding_client=app.state.embedding_client,
      lecture_service=app.state.lecture_service,
      summarize_service=app.state.summarize_service,
      redis_provider=app.state.redis_provider,
      evaluation_repo=app.state.evaluation_repo,
      student_persona_repo=app.state.student_persona_repo,
  )
  logger.info("All services and orchestrators loaded successfully")

  yield
  app.state.vdb_client.disconnect()
  await app.state.redis_provider.disconnect()
  app.state.mongo_client.close()
  
  

  

app = FastAPI(lifespan=lifespan)
app.add_exception_handler(AppException, app_exception_handler)
app.include_router(home_router.home_route)
app.include_router(grading_router.grading_route)
app.include_router(lecture_router.lecture_route)
app.include_router(session_router.session_route)
app.include_router(vectordb_router.vectordb_route)
app.include_router(assistant_router.assistant_route)
app.include_router(user_router.user_route)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run("main:app", host="0.0.0.0", port=81, reload=True)