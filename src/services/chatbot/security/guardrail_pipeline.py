from typing import Optional, Literal
from pydantic import BaseModel

from core.settings import Settings
from helpers.logger import get_chatbot_logger
from .injection_guard import InjectionGuard, InjectionResult
from .nemo_guard.rails_manager import NemoRailsManager, NemoRailResult

logger = get_chatbot_logger(__name__)


class GuardrailDecision(BaseModel):
    is_blocked: bool = False
    action: Literal[
        "proceed",
        "block_injection",
        "short_circuit_boundary",
    ] = "proceed"
    response_text: Optional[str] = None
    violation_type: Optional[str] = None
    score: float = 0.0


INJECTION_BLOCKED_MESSAGE = (
    "I cannot process this request due to safety and security policies. "
    "Please ask an academic question related to your courses or university regulations."
)


class GuardrailPipeline:


    def __init__(self, settings: Settings) -> None:
        logger.info("Initializing GuardrailPipeline eagerly...")
        self.injection_guard = InjectionGuard(
            hf_token=settings.HF_TOKEN,
            injection_threshold=0.5,
            jailbreak_threshold=0.5,
        )
        self.nemo_rails = NemoRailsManager()
        logger.info("GuardrailPipeline initialized successfully.")

    async def evaluate(self, query: str) -> GuardrailDecision:
        clean_query = (query or "").strip()
        if not clean_query:
            return GuardrailDecision(is_blocked=False, action="proceed")

        # Tier 1: Prompt Injection & Jailbreak Neural Detection (MetaGuard 86M)
        injection_result: InjectionResult = self.injection_guard.evaluate(clean_query)
        if not injection_result.is_safe:
            logger.warning(
                "GuardrailPipeline: Query blocked by Tier 1 (InjectionGuard). Type: %s, Score: %.4f",
                injection_result.violation_type,
                injection_result.score,
            )
            return GuardrailDecision(
                is_blocked=True,
                action="block_injection",
                response_text=INJECTION_BLOCKED_MESSAGE,
                violation_type=injection_result.violation_type,
                score=injection_result.score,
            )

        # Tier 2: Dialog Boundary Detection (NeMo Guardrails with local embeddings)
        nemo_result: Optional[NemoRailResult] = await self.nemo_rails.evaluate(clean_query)
        if nemo_result is not None and nemo_result.is_intercepted:
            logger.info("GuardrailPipeline: Short-circuiting query via Tier 2 (NeMo).")
            return GuardrailDecision(
                is_blocked=True,
                action="short_circuit_boundary",
                response_text=nemo_result.response_text,
            )

        # Passed all guardrails: query is safe and in-scope for LangGraph
        return GuardrailDecision(
            is_blocked=False,
            action="proceed",
        )
