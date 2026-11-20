from typing import Optional
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
    DB_BASE_URL: str
    QDRANT_URL: str
    REDIS_URL: str
    MONGODB_URL: str
    MONGO_DB_NAME: str 


    # APIs
    HF_TOKEN: Optional[str] = None
    COHERE_API_KEY: str
    LANGSMITH_API_KEY: str
    LANGSMITH_WORKSPACE: str = "nourmansour"
    PROMPT_ENVIRONMENT_TAG: str = "production"
    PROMPT_FETCH_REMOTE: bool = True
    OPENAI_API_URL: str
    OPENAI_API_KEY: str

    # LiteLLM Gateway Administration
    LITELLM_ADMIN_URL: str = "http://litellm:4000"
    LITELLM_MASTER_KEY: Optional[str] = None

    def get_litellm_master_key(self) -> str:
        return self.LITELLM_MASTER_KEY or self.OPENAI_API_KEY

    # Models
    GENERATION_BACKEND: str
    GENERATION_MODEL_ID: str

    # Per-node model routing (defaults to GENERATION_MODEL_ID if unset)
    ORCHESTRATOR_MODEL_ID: Optional[str] = None
    ANSWERING_MODEL_ID: Optional[str] = None
    PLANNER_MODEL_ID: Optional[str] = None
    REFLECTION_MODEL_ID: Optional[str] = None
    SUMMARY_MODEL_ID: Optional[str] = None
    PERSONA_MODEL_ID: Optional[str] = None
    GRADING_MODEL_ID: Optional[str] = None
    REWRITER_MODEL_ID: Optional[str] = None

    def get_model_for(self, node: str) -> str:
        """Return node-specific virtual model ID or fall back to GENERATION_MODEL_ID."""
        field_name = f"{node.upper()}_MODEL_ID"
        specific = getattr(self, field_name, None)
        return specific or self.GENERATION_MODEL_ID

    EMBEDDING_BACKEND: str
    EMBEDDING_MODEL_ID: str
    EMBEDDING_MODEL_SIZE: int

    VECTOR_DB_BACKEND: str
    VECTOR_DB_DISTANCE_METHOD: str

    class Config:
        env_file = ".env"



def get_settings() -> Settings:
    return Settings()