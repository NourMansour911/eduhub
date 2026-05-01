import re
from typing import Any, Dict, List, Sequence

from fastapi import Request
import numpy as np
import torch
from sentence_transformers import CrossEncoder
from sklearn.feature_extraction.text import TfidfVectorizer


class ScoringService:
    _SEMANTIC_WEIGHT = 0.6
    _KEYWORD_WEIGHT = 0.3
    _NUMBER_WEIGHT = 0.1
    _NUMBER_MISMATCH_PENALTY = 0.1
    _MAX_KEYWORDS_PER_CHUNK = 8
    _NUMBER_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

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
                "coverage": 0.0,
                "details": [],
            }

        if not student_chunks:
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
                "coverage": 0.0,
                "details": details,
            }

        total_weighted_score = 0.0
        covered_chunks = 0
        details: List[Dict[str, Any]] = []

        for teacher_chunk in prepared_teacher_chunks:
            pairs = [
                (teacher_chunk["text"], student_chunk.get("text", ""))
                for student_chunk in student_chunks
            ]
            reranker_scores = self.cross_encoder.predict(
                pairs,
                batch_size=32,
                show_progress_bar=False,
            )
            normalized_scores = self._normalize_reranker_scores(reranker_scores)

            best_index = int(np.argmax(normalized_scores))
            semantic_score = float(normalized_scores[best_index])
            student_chunk = student_chunks[best_index]
            covered_chunks += 1

            keyword_score = self._keyword_overlap_ratio(
                teacher_keywords=teacher_chunk["keywords"],
                student_keywords=student_chunk.get("keywords") or [],
            )

            number_score = self._number_score(
                teacher_numbers=teacher_chunk["numbers"],
                student_numbers=student_chunk.get("numbers") or [],
            )

            score = (
                (self._SEMANTIC_WEIGHT * semantic_score)
                + (self._KEYWORD_WEIGHT * keyword_score)
                + (self._NUMBER_WEIGHT * number_score)
            )

            if (
                teacher_chunk["numbers"]
                and (student_chunk.get("numbers") or [])
                and number_score == 0.0
            ):
                score -= self._NUMBER_MISMATCH_PENALTY

            score = self._clamp(score)
            total_weighted_score += teacher_chunk["weight"] * score

            details.append(
                {
                    "teacher_chunk": teacher_chunk["text"],
                    "best_student_chunk": student_chunk.get("text", ""),
                    "similarity": round(semantic_score, 4),
                    "score": round(score, 4),
                }
            )

        coverage = covered_chunks / len(prepared_teacher_chunks)
        final_score = self._clamp(total_weighted_score * coverage)

        return {
            "final_score": round(final_score, 4),
            "coverage": round(coverage, 4),
            "details": details,
        }

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

        teacher_keywords_map = self._extract_keywords_by_text(
            [item["text"] for item in prepared]
        )

        for index, item in enumerate(prepared):
            item["keywords"] = teacher_keywords_map[index]
            item["numbers"] = self._extract_numbers(item["text"])

        return prepared

    def _extract_keywords_by_text(self, texts: List[str]) -> Dict[int, List[str]]:
        if not texts:
            return {}

        try:
            vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=(1, 2),
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_]+\b",
            )
            matrix = vectorizer.fit_transform(texts)
        except ValueError:
            return {index: [] for index in range(len(texts))}

        feature_names = vectorizer.get_feature_names_out()
        keywords_map: Dict[int, List[str]] = {}

        for row_index in range(matrix.shape[0]):
            row = matrix.getrow(row_index)
            if row.nnz == 0:
                keywords_map[row_index] = []
                continue

            scored_terms = sorted(
                (
                    (feature_names[column_index], value)
                    for column_index, value in zip(row.indices, row.data)
                    if value > 0
                ),
                key=lambda item: (-item[1], item[0]),
            )
            keywords_map[row_index] = [
                term for term, _ in scored_terms[: self._MAX_KEYWORDS_PER_CHUNK]
            ]

        return keywords_map

    def _extract_numbers(self, text: str) -> List[str]:
        if not text:
            return []
        return [match.group(0) for match in self._NUMBER_PATTERN.finditer(text)]

    def _keyword_overlap_ratio(
        self,
        teacher_keywords: Sequence[str],
        student_keywords: Sequence[str],
    ) -> float:
        teacher_set = {keyword.lower() for keyword in teacher_keywords if keyword}
        if not teacher_set:
            return 1.0

        student_set = {keyword.lower() for keyword in student_keywords if keyword}
        overlap = teacher_set.intersection(student_set)
        return len(overlap) / len(teacher_set)

    def _number_score(
        self,
        teacher_numbers: Sequence[str],
        student_numbers: Sequence[str],
    ) -> float:
        teacher_set = set(teacher_numbers)
        student_set = set(student_numbers)

        if not teacher_set:
            return 1.0
        if not student_set:
            return 0.5
        if teacher_set == student_set:
            return 1.0
        if teacher_set.intersection(student_set):
            return 0.5
        return 0.0

    def _normalize_reranker_scores(self, scores: Sequence[float]) -> np.ndarray:
        values = np.asarray(scores, dtype=np.float32).reshape(-1)
        clipped = np.clip(values, -30.0, 30.0)
        return 1.0 / (1.0 + np.exp(-clipped))

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