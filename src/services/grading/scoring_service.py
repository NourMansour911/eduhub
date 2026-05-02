import re
from typing import Any, Dict, List, Sequence, Tuple

from fastapi import Request
import numpy as np
import torch
from sentence_transformers import CrossEncoder


class ScoringService:
    _SPACE_PATTERN = re.compile(r"\s+")
    _EPSILON = 1e-6

    def __init__(self, model_id: str, device: str):
        self.model_id = model_id
        self.device = self._resolve_device(device)
        self.cross_encoder = CrossEncoder(self.model_id, device=self.device)

    def calculate_weighted_score(
        self,
        reference_chunks: List[Dict[str, Any]],
        student_chunks: List[Dict[str, Any]],
        default_weight: float = 1.0,
    ) -> Dict[str, Any]:
        prepared_teacher_chunks = self._prepare_teacher_chunks(
            reference_chunks=reference_chunks,
            default_weight=default_weight,
        )
        if not prepared_teacher_chunks:
            return {
                "final_score": 0.0,
                "details": [],
            }

        student_texts = self._extract_student_texts(student_chunks)
        if not student_texts:
            details = [
                {
                    "teacher_chunk": chunk["text"],
                    "best_student_chunk": "",
                    "similarity": 0.0,
                    "score": 0.0,
                }
                for chunk in prepared_teacher_chunks
            ]
            return {
                "final_score": 0.0,
                "details": details,
            }

        score_matrix = self._calculate_score_matrix(
            teacher_chunks=prepared_teacher_chunks,
            student_texts=student_texts,
        )

        total_weighted_score = 0.0
        details: List[Dict[str, Any]] = []
        for teacher_index, teacher_chunk in enumerate(prepared_teacher_chunks):
            row = score_matrix[teacher_index]
            best_student_index = int(np.argmax(row))
            semantic_score = self._clamp(float(row[best_student_index]))
            best_student_chunk = student_texts[best_student_index]

            total_weighted_score += teacher_chunk["weight"] * semantic_score

            details.append(
                {
                    "teacher_chunk": teacher_chunk["text"],
                    "best_student_chunk": best_student_chunk,
                    "similarity": round(semantic_score, 4),
                    "score": round(semantic_score, 4),
                }
            )

        final_score = self._clamp(total_weighted_score)

        return {
            "final_score": round(final_score, 4),
            "details": details,
        }

    def _calculate_score_matrix(
        self,
        teacher_chunks: List[Dict[str, Any]],
        student_texts: List[str],
    ) -> np.ndarray:
        teacher_texts = [chunk["text"] for chunk in teacher_chunks]
        teacher_count = len(teacher_texts)
        student_count = len(student_texts)

        pairs: List[Tuple[str, str]] = []
        for teacher_text in teacher_texts:
            for student_text in student_texts:
                pairs.append((teacher_text, student_text))

        scores = self.cross_encoder.predict(
            pairs,
            batch_size=32,
            show_progress_bar=False,
        )
        normalized = self._normalize_scores(scores).reshape(teacher_count, student_count)
        return normalized

    def _prepare_teacher_chunks(
        self,
        reference_chunks: List[Dict[str, Any]],
        default_weight: float,
    ) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []

        for chunk in reference_chunks:
            text = str(chunk.get("text") or "").strip()
            if not text:
                continue

            metadata = chunk.get("metadata") or {}
            weight = metadata.get("weight", default_weight)
            try:
                weight = float(weight)
            except (TypeError, ValueError):
                weight = default_weight

            prepared.append(
                {
                    "text": text,
                    "weight": max(0.0, weight),
                }
            )

        if not prepared:
            return []

        total_weight = sum(item["weight"] for item in prepared)
        if total_weight <= 0:
            normalized_weight = 1.0 / len(prepared)
            for item in prepared:
                item["weight"] = normalized_weight
        else:
            for item in prepared:
                item["weight"] = item["weight"] / total_weight

        return prepared

    def _extract_student_texts(self, student_chunks: List[Dict[str, Any]]) -> List[str]:
        if not student_chunks:
            return []

        values = []
        for chunk in student_chunks:
            text = str(chunk.get("text") or "")
            normalized = self._SPACE_PATTERN.sub(" ", text).strip()
            if normalized:
                values.append(normalized)

        return values

    def _normalize_scores(self, scores: Sequence[float]) -> np.ndarray:
        values = np.asarray(scores, dtype=np.float32).reshape(-1)
        clipped = np.clip(values, -30.0, 30.0)
        sigmoid = 1.0 / (1.0 + np.exp(-clipped))
        return np.clip(sigmoid, 0.0, 1.0)

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