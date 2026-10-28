from typing import Optional, Literal
from pydantic import BaseModel
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from helpers.logger import get_chatbot_logger

logger = get_chatbot_logger(__name__)


class InjectionResult(BaseModel):
    is_safe: bool
    violation_type: Optional[Literal["injection", "jailbreak"]] = None
    score: float = 0.0
    label: str = "BENIGN"


class InjectionGuard:


    MODEL_ID = "meta-llama/Prompt-Guard-86M"

    def __init__(
        self,
        hf_token:str,
        injection_threshold: float = 0.5,
        jailbreak_threshold: float = 0.5,
    ) -> None:
        self.hf_token = hf_token
        self.injection_threshold = injection_threshold
        self.jailbreak_threshold = jailbreak_threshold

        logger.info("Initializing InjectionGuard (Meta Prompt-Guard-86M) eagerly...")
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_ID,
            token=self.hf_token,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.MODEL_ID,
            token=self.hf_token,
        )
        self.model.eval()
        logger.info("InjectionGuard (Prompt-Guard-86M) initialized and loaded into memory successfully.")

    def evaluate(self, query: str) -> InjectionResult:

        if not query or not query.strip():
            return InjectionResult(is_safe=True, label="BENIGN", score=1.0)

        clean_query = query.strip()

        inputs = self.tokenizer(
            clean_query,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )

        with torch.inference_mode():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=-1)[0]

        # Label mapping for Prompt-Guard-86M:
        # Index 0: LABEL_0 -> Benign
        # Index 1: LABEL_1 -> Injection
        # Index 2: LABEL_2 -> Jailbreak
        benign_score = float(probabilities[0].item())
        injection_score = float(probabilities[1].item())
        jailbreak_score = float(probabilities[2].item())

        if jailbreak_score >= self.jailbreak_threshold:
            logger.warning(
                "InjectionGuard: Jailbreak detected (score=%.4f): '%s'",
                jailbreak_score,
                clean_query[:80],
            )
            return InjectionResult(
                is_safe=False,
                violation_type="jailbreak",
                score=jailbreak_score,
                label="JAILBREAK",
            )

        if injection_score >= self.injection_threshold:
            logger.warning(
                "InjectionGuard: Prompt injection detected (score=%.4f): '%s'",
                injection_score,
                clean_query[:80],
            )
            return InjectionResult(
                is_safe=False,
                violation_type="injection",
                score=injection_score,
                label="INJECTION",
            )

        return InjectionResult(
            is_safe=True,
            violation_type=None,
            score=benign_score,
            label="BENIGN",
        )
