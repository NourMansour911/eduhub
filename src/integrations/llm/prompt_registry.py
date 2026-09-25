import warnings
from typing import Dict, Optional
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate
from core.settings import Settings
from helpers.logger import get_integrations_logger

# Suppress LangChain deserialization pending deprecation warning from LangSmith SDK
warnings.filterwarnings("ignore", message=".*allowed_objects.*")
try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
    warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
except ImportError:
    pass

logger = get_integrations_logger("prompt_registry")


class PromptRegistry:


    def __init__(self, settings: Settings, fallbacks: Dict[str, ChatPromptTemplate]):
        self.settings = settings
        self.fallbacks = fallbacks
        self._cache: Dict[str, ChatPromptTemplate] = {}
        self._sources: Dict[str, str] = {}

    def _build_repo_name(self, prompt_key: str) -> str:
        app_name = (self.settings.APP_NAME or "eduhub").strip().lower()
        tag = (self.settings.PROMPT_ENVIRONMENT_TAG or "production").strip()
        return f"{app_name}-{prompt_key}:{tag}"

    async def initialize(self) -> None:
        app_name = (self.settings.APP_NAME or "eduhub").strip().lower()
        tag = (self.settings.PROMPT_ENVIRONMENT_TAG or "production").strip()

        logger.info(
            "Initializing PromptRegistry (App: '%s', Tag: '%s', Fetch Remote: %s)...",
            app_name,
            tag,
            self.settings.PROMPT_FETCH_REMOTE,
        )

        client = Client(api_key=self.settings.LANGSMITH_API_KEY) if self.settings.LANGSMITH_API_KEY else None
        pulled_count = 0
        fallback_count = 0

        for key, fallback_template in self.fallbacks.items():
            if not self.settings.PROMPT_FETCH_REMOTE or not client:
                self._cache[key] = fallback_template
                self._sources[key] = "Code Fallback (Remote Fetch Disabled)"
                logger.info("  [Local Code] '%s' -> loaded from code fallback template", key)
                fallback_count += 1
                continue

            repo_name = self._build_repo_name(key)
            try:
                pulled_prompt = client.pull_prompt(repo_name)
                self._cache[key] = pulled_prompt
                self._sources[key] = f"LangSmith Hub ({repo_name})"
                logger.info("  [LangSmith Hub] '%s' -> pulled successfully from '%s'", key, repo_name)
                pulled_count += 1
            except Exception as exc:
                self._cache[key] = fallback_template
                self._sources[key] = "Code Fallback (Pull Failed)"
                logger.warning(
                    "  [Local Code] '%s' -> pull failed from '%s' (%s). Using local fallback template.",
                    key,
                    repo_name,
                    exc,
                )
                fallback_count += 1

        logger.info(
            "Prompt Registry Initialized: %d total prompts (%d from LangSmith Hub, %d from Code Fallbacks).",
            len(self._cache),
            pulled_count,
            fallback_count,
        )

    def get(self, prompt_key: str) -> ChatPromptTemplate:
        if prompt_key in self._cache:
            return self._cache[prompt_key]
        return self.fallbacks.get(prompt_key)

    def get_source(self, prompt_key: str) -> str:
        return self._sources.get(prompt_key, "Unknown / Direct Fallback")
