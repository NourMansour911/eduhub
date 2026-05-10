from pathlib import Path
import os
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

os.environ.setdefault("APP_NAME", "test_eduhub")
os.environ.setdefault("APP_VERSION", "test_0.0.0")
os.environ.setdefault("STORAGE_PATH", str(ROOT_DIR / "storage"))
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB_NAME", "test_eduhub")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("REDIS_URL", "redis://:test-redis-pass@localhost:6379/0")

os.environ.setdefault("COHERE_API_KEY", "test-cohere-key")
os.environ.setdefault("LANGSMITH_API_KEY", "test-langsmith-key")
os.environ.setdefault("OPENAI_API_URL", "https://api.openai.com/v1")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("GENERATION_BACKEND", "OPENAI")
os.environ.setdefault("GENERATION_MODEL_ID", "deepseek-v4-flash")
os.environ.setdefault("EMBEDDING_BACKEND", "HF")
os.environ.setdefault("EMBEDDING_MODEL_ID", "BAAI/bge-base-en-v1.5")
os.environ.setdefault("EMBEDDING_MODEL_SIZE", "768")

os.environ.setdefault("VECTOR_DB_BACKEND", "QDRANT")
os.environ.setdefault("VECTOR_DB_DISTANCE_METHOD", "Cosine")
os.environ.setdefault("AZURE_DOC_ENDPOINT", "https://test.cognitiveservices.azure.com/")
os.environ.setdefault("AZURE_DOC_KEY", "test-azure-key")

for path in (ROOT_DIR, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))