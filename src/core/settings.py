from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Configs
    APP_NAME: str
    APP_VERSION: str

    STORAGE_PATH: str

    AZURE_DOC_ENDPOINT:str
    AZURE_DOC_KEY: str

    # Database
    QDRANT_URL: str
    REDIS_URL: str
    MONGODB_URL: str
    MONGO_DB_NAME: str 


    # APIs
    COHERE_API_KEY: str
    LANGSMITH_API_KEY: str
    OPENAI_API_URL: str
    OPENAI_API_KEY: str

    # Models
    GENERATION_BACKEND: str
    GENERATION_MODEL_ID: str

    EMBEDDING_BACKEND: str
    EMBEDDING_MODEL_ID: str
    EMBEDDING_MODEL_SIZE: int

    VECTOR_DB_BACKEND: str
    VECTOR_DB_DISTANCE_METHOD: str

    class Config:
        env_file = ".env"



def get_settings() -> Settings:
    return Settings()