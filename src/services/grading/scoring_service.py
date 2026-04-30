import math
from typing import Any, Dict, List, Optional, Sequence


class ScoringService:
    def calculate_weighted_score(
        self,
        reference_chunks: List[Dict[str, Any]],
        student_vector: Sequence[float],
        default_weight: float = 1.0,
        decimals: Optional[int] = 1,
        boost_factor: float = 1.0,
    ) -> Dict[str, Any]:

        weighted_map = self._build_weighted_similarity_map(
            reference_chunks=reference_chunks,
            student_vector=student_vector,
            default_weight=default_weight,
        )

        total_weighted = sum(
            item.get("weighted_score", 0.0)
            for item in weighted_map
        )

        final_score = self._compute_final_score(
            score=total_weighted,
            boost_factor=boost_factor,
            decimals=decimals,
        )

        return {
            "weighted_map": weighted_map,
            "raw_weighted_total": total_weighted,
            "final_score": final_score,
        }

    def _compute_final_score(
        self,
        score: float,
        boost_factor: float = 1.0,
        decimals: Optional[int] = 1,
        input_min: float = 0.0,
        input_max: float = 1.0,
        output_min: float = 0.0,
        output_max: float = 100.0,
        clamp: bool = True,
    ) -> float:

        if input_max == input_min:
            raise ValueError("input_min and input_max must be different")

        
        boosted = score + 0.1

        if clamp:
            boosted = max(0.0, min(1.0, boosted))

        boosted = boosted * boost_factor

        if clamp:
            boosted = max(0.0, min(1.0, boosted))

        normalized = (boosted - input_min) / (input_max - input_min)

        scaled = output_min + normalized * (output_max - output_min)

        return round(scaled, decimals) if decimals is not None else scaled

    def _build_weighted_similarity_map(
        self,
        reference_chunks: List[Dict[str, Any]],
        student_vector: Sequence[float],
        default_weight: float = 1.0,
    ) -> List[Dict[str, Any]]:

        weighted_results: List[Dict[str, Any]] = []

        for chunk in reference_chunks:
            vector = chunk.get("vector")
            if not vector:
                continue

            similarity = self._cosine_similarity(
                student_vector,
                vector
            )


            similarity = max(0.0, min(1.0, similarity))

            metadata = chunk.get("metadata") or {}

            weight = metadata.get("weight", default_weight)

            try:
                weight = float(weight)
            except (TypeError, ValueError):
                weight = default_weight

            weighted_results.append(
                {
                    "id": chunk.get("id"),
                    "similarity": similarity,
                    "weight": weight,
                    "weighted_score": similarity * weight,
                }
            )

        return weighted_results

    def _cosine_similarity(
        self,
        vector_a: Sequence[float],
        vector_b: Sequence[float],
    ) -> float:

        if not vector_a or not vector_b:
            return 0.0

        if len(vector_a) != len(vector_b):
            raise ValueError("Vector sizes must match")

        dot_product = 0.0
        norm_a = 0.0
        norm_b = 0.0

        for a_value, b_value in zip(vector_a, vector_b):
            dot_product += a_value * b_value
            norm_a += a_value * a_value
            norm_b += b_value * b_value

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))


def get_scoring_service() -> ScoringService:
    return ScoringService()