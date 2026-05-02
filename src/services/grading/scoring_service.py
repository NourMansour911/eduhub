from typing import Any, Dict, List, Tuple

from fastapi import Request
import torch
from sentence_transformers import CrossEncoder


class ScoringService:

    def __init__(self, model_id: str, device: str):
        self.model_id = model_id
        self.device = self._resolve_device(device)
        self.cross_encoder = CrossEncoder(self.model_id, device=self.device)

    def calculate_weighted_score(
        self,
        reference_chunks: List[Dict[str, Any]],
        student_answer: str,
        default_weight: float = 1.0,
    ) -> Dict[str, Any]:

        teacher_list = self._prepare_teacher_chunks(reference_chunks, default_weight)

        if not teacher_list or not student_answer:
            return {
                "final_score": 0.0,
                "details": []
            }

        pairs: List[Tuple[str, str]] = [
            (t["text"], student_answer) for t in teacher_list
        ]

        raw_scores = self.cross_encoder.predict(
            pairs,
            batch_size=32,
            show_progress_bar=False
        )

        weighted_sum = 0.0
        max_possible = 0.0
        details: List[Dict[str, Any]] = []

        for teacher_chunk, raw in zip(teacher_list, raw_scores):
            score = self._clamp(float(raw))
            weight = teacher_chunk.get("weight", default_weight)

            weighted_sum += score * weight
            max_possible += weight

            details.append({
                "teacher_chunk": teacher_chunk["text"],
                "similarity": round(score, 4),
                "weight": round(weight, 4),
                "final_score": round(score * weight, 4),
            })

        final_score = (
            weighted_sum / max_possible
            if max_possible > 0 else 0.0
        )

        return {
            "final_score": round(final_score, 4),
            "details": details,
        }

    def _prepare_teacher_chunks(
        self,
        reference_chunks: List[Dict[str, Any]],
        default_weight: float
    ) -> List[Dict[str, Any]]:

        prepared: List[Dict[str, Any]] = []

        for chunk in reference_chunks:
            text = str(chunk.get("text") or "").strip()
            if not text:
                continue

            metadata = chunk.get("metadata") or {}
            try:
                weight = float(metadata.get("weight", default_weight))
            except Exception:
                weight = default_weight

            prepared.append({
                "text": text,
                "weight": max(0.0, weight)
            })

        if not prepared:
            return []

        total = sum(c["weight"] for c in prepared)

        if total <= 0:
            for c in prepared:
                c["weight"] = 1.0 / len(prepared)
        else:
            for c in prepared:
                c["weight"] /= total

        return prepared

    def _resolve_device(self, preferred_device: str) -> str:
        normalized = (preferred_device or "cuda").strip().lower()

        if normalized == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"

        if normalized.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError(
                "CROSS_ENCODER_DEVICE is set to cuda but no GPU is available"
            )

        return normalized

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


def get_scoring_service(request: Request) -> ScoringService:
    return request.app.state.scoring_service