import asyncio
import time
import inspect
import copy
from functools import wraps
from typing import Any, Dict, List, Optional, AsyncGenerator

from openai import OpenAI, AsyncOpenAI, APIError, RateLimitError

from ..llm_interface import LLMInterface
from helpers import get_logger
from ..llm_enums import OpenAIEnums
from ..llm_exceptions import (
    LLMInitializationException,
    LLMModelNotSetException,
    LLMAPINotAvailableException,
    LLMRateLimitException,
    LLMInvalidResponseException,
)

logger = get_logger(__name__)


def retry(func):
    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(self.max_retries):
                try:
                    return await func(self, *args, **kwargs)

                except RateLimitError as e:
                    logger.warning(f"[Retry] RateLimit attempt {attempt+1}")
                    last_exception = LLMRateLimitException(
                        model_id=kwargs.get("model") or self.generation_model,
                        retry_after=getattr(e, "reset", None),
                    )

                except APIError as e:
                    logger.warning(f"[Retry] APIError attempt {attempt+1}")
                    last_exception = LLMAPINotAvailableException(
                        provider="OpenAI",
                        api_endpoint="chat/completions",
                        network_error=str(e),
                    )

                except Exception as e:
                    logger.warning(f"[Retry] Unexpected error: {e}")
                    last_exception = e

                await asyncio.sleep(2 ** attempt)

            raise last_exception

        return async_wrapper

    else:

        @wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(self.max_retries):
                try:
                    return func(self, *args, **kwargs)

                except RateLimitError as e:
                    logger.warning(f"[Retry] RateLimit attempt {attempt+1}")
                    last_exception = LLMRateLimitException(
                        model_id=kwargs.get("model") or self.generation_model,
                        retry_after=getattr(e, "reset", None),
                    )

                except APIError as e:
                    logger.warning(f"[Retry] APIError attempt {attempt+1}")
                    last_exception = LLMAPINotAvailableException(
                        provider="OpenAI",
                        api_endpoint="chat/completions",
                        network_error=str(e),
                    )

                except Exception as e:
                    logger.warning(f"[Retry] Unexpected error: {e}")
                    last_exception = e

                time.sleep(2 ** attempt)

            raise last_exception

        return sync_wrapper


class OpenAIProvider(LLMInterface):
    def __init__(
        self,
        api_key: str,
        timeout: int,
        max_retries: int ,
        default_temperature: float,
        default_max_tokens: int ,
        api_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.max_retries = max_retries

        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens

        self.generation_model: Optional[str] = None
        self.embedding_model: Optional[str] = None
        self.embedding_size: Optional[int] = None

        try:
            self.client = OpenAI(api_key=api_key, base_url=api_url)
            self.async_client = AsyncOpenAI(api_key=api_key, base_url=api_url)
            logger.info("OpenAI clients initialized")
        except Exception as e:
            raise LLMInitializationException(provider="OpenAI", init_error=str(e))

    def set_generation_model(self, model_id: str):
        self.generation_model = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model = model_id
        self.embedding_size = embedding_size

    def _build_messages(self, prompt: str, chat_history: List[Dict] = None):
        messages = copy.deepcopy(chat_history) if chat_history else []
        messages.append({"role": OpenAIEnums.USER.value, "content": prompt})
        return messages

    def _validate_generation_model(self, model: Optional[str]):
        final_model = model or self.generation_model
        if not final_model:
            raise LLMModelNotSetException(
                operation="generation",
                model_type="generation",
                provider="OpenAI",
            )
        return final_model

    def _validate_embedding_model(self, model: Optional[str]):
        final_model = model or self.embedding_model
        if not final_model:
            raise LLMModelNotSetException(
                operation="embedding",
                model_type="embedding",
                provider="OpenAI",
            )
        return final_model

    @retry
    def generate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        chat_history: List[Dict] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        model_to_use = self._validate_generation_model(model)

        response = self.client.chat.completions.create(
            model=model_to_use,
            messages=self._build_messages(prompt, chat_history),
            temperature=temperature or self.default_temperature,
            max_tokens=max_tokens or self.default_max_tokens,
            timeout=self.timeout,
        )

        if not response or not response.choices:
            raise LLMInvalidResponseException(
                model_id=model_to_use,
                response_data=str(response),
                validation_error="Empty response",
            )

        content = response.choices[0].message.content
        if not content:
            raise LLMInvalidResponseException(
                model_id=model_to_use,
                response_data=str(response),
                validation_error="No content",
            )

        return content

    @retry
    async def agenerate_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        chat_history: List[Dict] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        model_to_use = self._validate_generation_model(model)

        response = await self.async_client.chat.completions.create(
            model=model_to_use,
            messages=self._build_messages(prompt, chat_history),
            temperature=temperature or self.default_temperature,
            max_tokens=max_tokens or self.default_max_tokens,
            timeout=self.timeout,
        )

        if not response or not response.choices:
            raise LLMInvalidResponseException(
                model_id=model_to_use,
                response_data=str(response),
                validation_error="Empty response",
            )

        content = response.choices[0].message.content
        if not content:
            raise LLMInvalidResponseException(
                model_id=model_to_use,
                response_data=str(response),
                validation_error="No content",
            )

        return content

    @retry
    async def stream_text(
        self,
        prompt: str,
        model: Optional[str] = None,
        chat_history: List[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        model_to_use = self._validate_generation_model(model)

        stream = await self.async_client.chat.completions.create(
            model=model_to_use,
            messages=self._build_messages(prompt, chat_history),
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
                
    @retry
    async def embed_text(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> List[float]:

        model_to_use = self._validate_embedding_model(model)

        try:
            response = await self.async_client.embeddings.create(
                model=model_to_use,
                input=[text],
            )

        except Exception as e:
            raise LLMAPINotAvailableException(
                provider="OpenAI",
                api_endpoint="embeddings",
                network_error=str(e),
            )

        if not response or not response.data:
            raise LLMInvalidResponseException(
                model_id=model_to_use,
                response_data=str(response),
                validation_error="Empty embedding response",
            )

        embedding = response.data[0].embedding

        if not embedding:
            raise LLMInvalidResponseException(
                model_id=model_to_use,
                response_data=str(response),
                validation_error="No embedding returned",
            )

        return embedding