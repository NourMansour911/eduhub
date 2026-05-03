import re
from typing import Any, Dict, List

from fastapi import Request
import torch
from sentence_transformers import CrossEncoder


class ScoringService:

    def __init__(self, model_id: str, device: str):
        self.model_id = model_id
        self.device = self._resolve_device(device)
        self.cross_encoder = CrossEncoder(self.model_id, device=self.device)

    # UTILS
    def _word_count(self, text: str) -> int:
        return len(text.split())

    # MAIN SCORING
    def calculate_weighted_score(
        self,
        reference_chunks: List[Dict[str, Any]],
        student_answer: str,
        default_weight: float = 1.0,
    ) -> Dict[str, Any]:

        teacher_list = self._prepare_teacher_chunks(reference_chunks, default_weight)
        student_chunks = self._chunk_student_answer(student_answer)

        if not teacher_list or not student_chunks:
            return {"final_score": 0.0, "details": []}

        weighted_sum = 0.0
        max_possible = 0.0
        details: List[Dict[str, Any]] = []

        # LENGTH BASELINE (RELATIVE)
        teacher_full = " ".join([t["text"] for t in teacher_list])
        student_full = " ".join(student_chunks)

        teacher_len = self._word_count(teacher_full)
        student_len = self._word_count(student_full)

        if teacher_len > 0:
            length_ratio = student_len / teacher_len
            length_penalty = min(1.0, length_ratio)
        else:
            length_penalty = 1.0

        # duplication penalty
        unique_chunks = list(set(student_chunks))
        dup_penalty = len(unique_chunks) / len(student_chunks)

        # soft global penalty
        global_penalty = 0.7 + 0.3 * (length_penalty * dup_penalty)

        # CORE SCORING
        for teacher_chunk in teacher_list:

            pairs = [
                (teacher_chunk["text"], s_chunk)
                for s_chunk in student_chunks
            ]

            raw_scores = self.cross_encoder.predict(
                pairs,
                batch_size=32,
                show_progress_bar=False
            )

            scores = list(raw_scores)

            # DYNAMIC NORMALIZATION (CRITICAL)
            min_s = min(scores)
            max_s = max(scores)

            if max_s - min_s > 1e-6:
                scores = [(s - min_s) / (max_s - min_s) for s in scores]
            else:
                scores = [0.5 for _ in scores]

            # HYBRID AGGREGATION
            top_k = max(1, int(0.2 * len(scores)))
            sorted_scores = sorted(scores, reverse=True)

            top_scores = sorted_scores[:top_k]
            top_k_score = sum(top_scores) / len(top_scores)

            best_score = sorted_scores[0]

            score = 0.6 * best_score + 0.4 * top_k_score

            # SOFT COVERAGE
            coverage = sum(1 for s in scores if s > 0.5) / len(scores)
            score = 0.7 * score + 0.3 * coverage

            # BASELINE LIFT (IMPORTANT)
            score = 0.2 + 0.8 * score

            weight = teacher_chunk.get("weight", default_weight)

            weighted_sum += score * weight
            max_possible += weight

            details.append({
                "teacher_chunk": teacher_chunk["text"],
                "best_score": round(float(best_score), 4),
                "top_k_score": round(float(top_k_score), 4),
                "coverage": round(float(coverage), 4),
                "final_chunk_score": round(float(score), 4),
                "weight": round(weight, 4),
                "weighted_score": round(float(score * weight), 4),
            })

        base_score = (
            weighted_sum / max_possible
            if max_possible > 0 else 0.0
        )

        # APPLY SOFT GLOBAL PENALTY
        final_score = base_score * global_penalty

        return {
            "final_score": round(float(final_score), 4),
            "base_score": round(float(base_score), 4),
            "length_penalty": round(length_penalty, 4),
            "dup_penalty": round(dup_penalty, 4),
            "global_penalty": round(global_penalty, 4),
            "details": details,
        }

    # STUDENT CHUNKING
    def _chunk_student_answer(self, text: str) -> List[str]:
        if not text:
            return []

        text = text.strip()
        paragraphs = re.split(r'\n\s*\n', text)

        chunks: List[str] = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            words = para.split()

            if len(words) <= 60:
                chunks.append(para)
                continue

            sentences = re.split(r'(?<=[.!?])\s+', para)

            window = []
            window_size = 3

            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue

                window.append(sent)

                if len(window) >= window_size:
                    chunks.append(" ".join(window))
                    window = window[-1:]

            if window:
                chunks.append(" ".join(window))

        chunks = [c.strip() for c in chunks if c.strip()]
        return chunks if chunks else [text]

    # TEACHER PREPARATION
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

    # DEVICE
    def _resolve_device(self, preferred_device: str) -> str:
        normalized = (preferred_device or "cuda").strip().lower()

        if normalized == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"

        if normalized.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available")

        return normalized


def get_scoring_service(request: Request) -> ScoringService:
    return request.app.state.scoring_service