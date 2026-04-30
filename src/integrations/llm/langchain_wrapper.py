# integrations/llm/llm_factory.py

from typing import Optional
from langchain_openai import ChatOpenAI

class LCOpenAI:
    def __init__(self, api_key: str, api_url: Optional[str] = None):
        self.api_key = api_key
        self.api_url = api_url

    def get_langchain_llm(
        self,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = None,
    ) -> ChatOpenAI:

        return ChatOpenAI(
            model=model,
            api_key=self.api_key,
            base_url=self.api_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )