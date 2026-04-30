from .providers import QdrantDBProvider
from helpers import get_logger
from core.settings import Settings

logger = get_logger(__name__)




class VectorDBFactory:
    def __init__(self,settings: Settings):
        self.settings = settings
    
    def create(self, provider: str):
        if provider == "QDRANT":
            return QdrantDBProvider(
                distance_method=self.settings.VECTOR_DB_DISTANCE_METHOD,
                vector_size=self.settings.EMBEDDING_MODEL_SIZE,
                url=self.settings.QDRANT_URL
            )
        
        return None
