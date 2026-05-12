from .providers import  HuggingFaceProvider

from helpers import get_logger
from typing import Optional
logger = get_logger(__name__)
class LLMFactory:

    
    def create(self,api_key: str ,provider: str = "OPENAI",api_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        default_temperature: float = 0.7,
        default_max_tokens: int = 500
        ) :

        if provider == "HF":
            return HuggingFaceProvider()

        return None

