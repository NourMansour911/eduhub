from pathlib import Path
from typing import Optional, Set
from pydantic import BaseModel
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.testing import fake_model

from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


class NemoRailResult(BaseModel):
    is_intercepted: bool
    response_text: str = ""


INTERCEPT_RAIL_NAMES: Set[str] = {"greeting", "off topic"}


class NemoRailsManager:
    """
    Manages NeMo Guardrails for conversational boundary enforcement:
    - Pure greetings handling (instant warm Nova response)
    - Off-topic redirection (instant educational scope redirection)
    
    Uses local sentence-transformers embeddings for intent matching (0 LLM cost).
    Eagerly loaded on startup (Singleton pattern).
    """

    def __init__(self, config_dir: Optional[str] = None) -> None:
        if config_dir is None:
            config_dir = str(Path(__file__).parent / "config")
        self.config_dir = config_dir

        logger.info("Initializing NemoRailsManager eagerly from %s...", self.config_dir)
        self.config = RailsConfig.from_path(self.config_dir)
        self.rails = LLMRails(self.config, llm=fake_model)
        logger.info("NemoRailsManager loaded and initialized successfully.")

    async def evaluate(self, query: str) -> Optional[NemoRailResult]:
        clean_query = (query or "").strip()
        if not clean_query:
            return None

        messages = [{"role": "user", "content": clean_query}]
        result = await self.rails.generate_async(
            messages=messages,
            options={"log": {"activated_rails": True}},
        )

        # Extract content from GenerationResponse
        if hasattr(result, "response") and result.response:
            first_msg = result.response[0]
            content = first_msg.get("content", "") if isinstance(first_msg, dict) else getattr(first_msg, "content", "")
        elif isinstance(result, dict):
            content = result.get("content", "")
        else:
            content = str(result)

        content_clean = (content or "").strip()

        # Extract activated rail names from result.log
        activated_rails = []
        if hasattr(result, "log") and hasattr(result.log, "activated_rails"):
            activated_rails = [getattr(r, "name", "") for r in (result.log.activated_rails or [])]
        elif isinstance(result, dict) and "log" in result:
            raw_rails = result["log"].get("activated_rails", [])
            activated_rails = [
                r.get("name", "") if isinstance(r, dict) else getattr(r, "name", "")
                for r in raw_rails
            ]

        # Check if any interception rail (greeting / off topic) was activated
        if any(name in INTERCEPT_RAIL_NAMES for name in activated_rails):
            logger.info("NemoRailsManager: Query intercepted by rail: '%s' (activated=%s)", clean_query[:60], activated_rails)
            return NemoRailResult(
                is_intercepted=True,
                response_text=content_clean,
            )

        return None
