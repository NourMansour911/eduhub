from typing import Any, Optional

import numpy as np

from helpers.logger import get_chatbot_logger
from integrations.llm import LLMInterface

logger = get_chatbot_logger(__name__)


class NameResolver:
	def __init__(self, embedding_client: Optional[LLMInterface]) -> None:
		self.embedding_client = embedding_client

	async def resolve_best_match_with_threshold(
		self,
		items: list[dict[str, Any]],
		query_name: str,
		*,
		name_key: str = "name",
		id_key: str = "id",
		threshold: float = 0.75,
	) -> Optional[dict[str, Any]]:
		logger.info("[NameResolver] resolve_best_match_with_threshold | query: '%s' | candidates: %d | threshold: %.2f", query_name, len(items), threshold)
		match = await self.resolve_best_match(
			items=items,
			query_name=query_name,
			name_key=name_key,
			id_key=id_key,
		)
		if match is None:
			logger.info("[NameResolver] No match found for query: '%s'", query_name)
			return None

		confidence_score = float(match.get("confidence_score") or 0.0)
		if confidence_score < threshold:
			logger.info("[NameResolver] Best match '%s' (id=%s) rejected — score %.4f below threshold %.2f",
						match.get("name"), match.get("id"), confidence_score, threshold)
			return None

		logger.info("[NameResolver] Resolved '%s' → name='%s' | id=%s | confidence=%.4f",
					query_name, match.get("name"), match.get("id"), confidence_score)
		return {
			"id": match.get("id"),
			"name": match.get("name"),
			"confidence_score": confidence_score,
		}

	async def resolve_best_match(
		self,
		items: list[dict[str, Any]],
		query_name: str,
		*,
		name_key: str = "name",
		id_key: str = "id",
	) -> Optional[dict[str, Any]]:
		query = (query_name or "").strip()
		if not items or not query or self.embedding_client is None:
			logger.info("[NameResolver] resolve_best_match skipped — items=%d, query='%s', client=%s",
						len(items), query, self.embedding_client is not None)
			return None

		candidate_items: list[dict[str, Any]] = []
		candidate_names: list[str] = []
		for item in items:
			candidate_name = str(item.get(name_key, "")).strip()
			if not candidate_name:
				continue
			candidate_items.append(item)
			candidate_names.append(candidate_name)

		if not candidate_items:
			return None

		logger.info("[NameResolver] Embedding %d candidates for query '%s': %s",
					len(candidate_names), query, candidate_names)
		embeddings = await self.embedding_client.embed_text([query, *candidate_names])
		if not embeddings:
			return None

		query_embedding = np.asarray(embeddings[0], dtype=float)
		candidate_embeddings = [np.asarray(vector, dtype=float) for vector in embeddings[1:]]
		if not candidate_embeddings:
			return None

		best_index = max(
			range(len(candidate_embeddings)),
			key=lambda idx: NameResolver._cosine_similarity(query_embedding, candidate_embeddings[idx]),
		)
		best_score = NameResolver._cosine_similarity(query_embedding, candidate_embeddings[best_index])

		logger.info("[NameResolver] Best raw match: '%s' | cosine_score=%.4f",
					candidate_names[best_index], best_score)

		resolved_item = dict(candidate_items[best_index])
		resolved_item["id"] = resolved_item.get(id_key)
		resolved_item["name"] = candidate_names[best_index]
		resolved_item["requested_name"] = query
		resolved_item["confidence_score"] = best_score
		return resolved_item

	@staticmethod
	def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
		denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
		if denominator == 0.0:
			return 0.0
		return float(np.dot(left, right) / denominator)


