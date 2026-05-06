
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from core import app_exception_handler,get_settings
from core.app_exceptions import AppException
from contextlib import asynccontextmanager
from helpers.logger import get_logger
from repositories import AnswerRepo
from repositories.mongo_bootstrap import init_mongo_resources
from routers import grading_router, home_router, vectordb_router
from integrations.vector_db import VectorDBFactory
from integrations.llm import LLMFactory,LCOpenAI
import os

from src.repositories.lecture_repo import LectureRepo

settings = get_settings()
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"] = settings.APP_NAME

OPENAI_API_KEYS = settings.OPENAI_API_KEY.split(",")
logger = get_logger(__name__,level="debug")



@asynccontextmanager
async def lifespan(app: FastAPI):
  # Exception handler
  app.add_exception_handler(AppException, app_exception_handler)
  
   # VectorDB client
  vdb_provider_factory = VectorDBFactory(settings)
  app.state.vdb_client = vdb_provider_factory.create(provider=settings.VECTOR_DB_BACKEND)
  app.state.vdb_client.connect()
  collections = app.state.vdb_client.list_all_collections()
  logger.info(f"VectorDB client loaded successfully")
  logger.info(f"VectorDB Collections: {collections}")
  
  
  
  # LLM clients
  ## Embedding client
  llm_provider_factory = LLMFactory()
  app.state.embedding_client = llm_provider_factory.create(api_key="hf",provider=settings.EMBEDDING_BACKEND)
  app.state.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_MODEL_SIZE)
  logger.info("Embedding client loaded successfully")
  ## LangChain client
  app.state.langchain_client = LCOpenAI(api_key=OPENAI_API_KEYS[3],api_url=settings.OPENAI_API_URL)
  logger.info("LangChain client loaded successfully")

  # Mongo client
  app.state.mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
  app.state.mongo_db = app.state.mongo_client[settings.MONGO_DB_NAME]
  mongo_repos = await init_mongo_resources(
    app.state.mongo_db,
    [AnswerRepo, LectureRepo],
  )
  app.state.answer_repo = mongo_repos["AnswerRepo"]
  app.state.lecture_repo = mongo_repos["LectureRepo"]
  logger.info("Mongo repositories loaded successfully")


  yield
  app.state.vdb_client.disconnect()
  app.state.mongo_client.close()
  
  

  

app = FastAPI(lifespan=lifespan)
app.add_exception_handler(AppException, app_exception_handler)
app.include_router(home_router.home_route)
app.include_router(grading_router.grading_route)
app.include_router(vectordb_router.vectordb_route)
