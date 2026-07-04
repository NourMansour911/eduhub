from typing import Any, Dict, List, Optional

from core import Settings, get_settings
from core.request_dependencies import (
	get_embedding_client,
	get_langchain_client,
	get_vdb_client,
)
from fastapi import Depends
from helpers.logger import get_chatbot_logger
from integrations.llm import LCOpenAI, LLMInterface
from integrations.vector_db import VectorDBInterface

from dtos.vdb_payload_dto import VDBSearchResultPayload
from services.vdb_service.vdb_exceptions import VectorDBException
from services.vdb_service.vdb_exceptions import VectorizationError
from services.service_exceptions import ServiceException

from .query_rewriting_chain import build_query_rewriting_chain
from .reranker import Reranker
from .retrieval import Retrieval


logger = get_chatbot_logger("chatbot_retrieval_search_service")


class SearchService:
	def __init__(
		self,
		vdb_client: VectorDBInterface,
		embedding_client: LLMInterface,
		settings: Settings,
		langchain_client: LCOpenAI,
	):
		self.vdb_client = vdb_client
		self.embedding_client = embedding_client
		self.settings = settings
		self.langchain_client = langchain_client

	async def search_by_metadata_field(
		self,
		collection_name: str,
		field_name: str,
		field_value: Any,
		limit: int = 10,
		query_text: str = "",
		rewrite_mode: str = "general",
	) -> List[VDBSearchResultPayload]:
		if not (query_text and query_text.strip()):
			raise ServiceException(details={"operation": "search_by_metadata_field", "error": "query_text is required"})

		search_query = query_text.strip()
		return await self._search(
			collection_name=collection_name,
			query=search_query,
			limit=limit,
			filters=[{"field": field_name, "value": field_value, "op": "eq"}],
			rewrite_mode=rewrite_mode,
		)

	async def search_by_metadata_range(
		self,
		collection_name: str,
		field_name: str,
		gte: Any = None,
		lte: Any = None,
		limit: int = 10,
		query_text: str = "",
	) -> List[VDBSearchResultPayload]:
		range_value: Dict[str, Any] = {}
		if gte is not None:
			range_value["gte"] = gte
		if lte is not None:
			range_value["lte"] = lte

		if not range_value:
			return []

		if not (query_text and query_text.strip()):
			raise ServiceException(details={"operation": "search_by_metadata_range", "error": "query_text is required"})

		search_query = query_text.strip()
		return await self._search(
			collection_name=collection_name,
			query=search_query,
			limit=limit,
			filters=[{"field": field_name, "value": range_value, "op": "range"}],
		)

	async def _search(
		self,
		collection_name: str,
		query: str,
		rewritten_queries: Optional[List[str]] = None,
		rewrite_mode: Optional[str] = None,
		limit: int = 10,
		filters: Optional[Any] = None,
	) -> List[VDBSearchResultPayload]:
		query = (query or "").strip()

		logger.info(f"[Retrieval] Initiating search. Original Query: '{query}' | Rewrite Mode: {rewrite_mode} | Collection: {collection_name}")
		rewritten_queries = await self._resolve_rewritten_queries(
			query=query,
			rewrite_mode=rewrite_mode,
			rewritten_queries=rewritten_queries,
		)
		all_queries = [query] + [q for q in rewritten_queries if q and q.strip()]
		logger.info(f"[Retrieval] Resolved queries for search execution: {all_queries}")

		base_k = max(1, limit)
		candidate_k = min(base_k * 4, 50)

		try:
			retrieval = Retrieval(
				embedding_client=self.embedding_client,
				vdb_client=self.vdb_client,
			)
			candidates = await retrieval.retrieve_multi_query(
				queries=all_queries,
				collection_name=collection_name,
				top_k=candidate_k,
				filters=filters,
			)
		except ServiceException:
			raise
		except Exception as exc:
			raise VectorDBException(
				details={
					"operation": "retrieve_multi_query",
					"collection_name": collection_name,
					"error": str(exc),
					"type": type(exc).__name__,
				},
			) from exc

		if not candidates:
			logger.info(f"[Retrieval] Retrieved 0 candidates for queries: {all_queries}")
			return []

		logger.info(f"[Retrieval] Retrieved {len(candidates)} candidate chunks from Vector DB.")
		for idx, candidate in enumerate(candidates, start=1):
			text_snippet = str(candidate.get("text", ""))[:100].replace("\n", " ")
			logger.info(
				f"[Retrieval] Candidate {idx}: Score: {candidate.get('score')} | "
				f"ID: {candidate.get('id')} | Snippet: '{text_snippet}...' | "
				f"Metadata: {candidate.get('metadata')}"
			)

		final_top_k = max(1, int(limit or 10))

		cohere_key = self.settings.COHERE_API_KEY
		if not cohere_key:
			results = self._normalize_vdb_results(candidates[:final_top_k])
			logger.info(f"[Retrieval] Cohere Reranking skipped (no API key). Returning top {len(results)} base candidate results.")
			return results

		try:
			logger.info(f"[Retrieating/Reranking] Sending {len(candidates)} candidates to Cohere Reranker with query: '{query}'")
			reranker = Reranker(api_key=cohere_key)
			reranked = await reranker.rerank(
				query=query,
				documents=candidates,
				top_k=final_top_k,
			)
			logger.info(f"[Retrieating/Reranking] Reranker returned {len(reranked)} results.")
			for idx, item in enumerate(reranked[:final_top_k], start=1):
				text_snippet = str(item.get("text", ""))[:100].replace("\n", " ")
				logger.info(
					f"[Retrieating/Reranking] Reranked Top {idx}: Score: {item.get('score')} | "
					f"ID: {item.get('id')} | Snippet: '{text_snippet}...'"
				)
			return self._normalize_vdb_results(reranked[:final_top_k])
		except ServiceException:
			raise
		except Exception as exc:
			logger.warning(
				"Rerank failed; falling back to retrieval results",
				extra={
					"operation": "search.rerank",
					"collection_name": collection_name,
					"error": str(exc),
					"type": type(exc).__name__,
				},
			)
			return self._normalize_vdb_results(candidates[:final_top_k])

	def _normalize_vdb_results(self, results: List[Dict[str, Any]]) -> List[VDBSearchResultPayload]:
		normalized_results: List[VDBSearchResultPayload] = []
		for item in results or []:
			metadata = item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {}
			payload = VDBSearchResultPayload(
				id=str(item.get("id", "")),
				relevance_score=round(item.get("score"), 2),
				text=str(item.get("text", "")),
				metadata=metadata,
			)
			normalized_results.append(payload)
		return normalized_results


	async def _resolve_rewritten_queries(
		self,
		query: str,
		rewrite_mode: Optional[str] = None,
		rewritten_queries: Optional[List[str]] = None,
	) -> List[str]:
		cleaned_queries = [q.strip() for q in (rewritten_queries or []) if q and q.strip()]
		mode_key = (rewrite_mode or "").strip().lower()

		if not query or not mode_key:
			return cleaned_queries

		rewrite_count = 3
		if mode_key == "session_summary":
			rewrite_count = 2
		elif mode_key == "lecture_search":
			rewrite_count = 4

		try:
			llm = self.langchain_client.get_langchain_llm(
				model=self.settings.GENERATION_MODEL_ID,
				temperature=0.2,
				max_tokens=256,
			)
			rewrite_chain = build_query_rewriting_chain(llm)
			response = await rewrite_chain.ainvoke(
				{
					"query": query,
					"rewrite_mode": mode_key,
					"rewrite_count": rewrite_count,
				},
				config={"run_name": f"Query Rewriting Chain Run ({mode_key})"}
			)
			generated = getattr(response, "rewritten_queries", []) or []
		except Exception as exc:
			logger.warning(
				"Query rewriting failed; continuing with explicit rewritten queries only",
				extra={
					"operation": "search.rewrite",
					"rewrite_mode": mode_key,
					"error": str(exc),
					"type": type(exc).__name__,
				},
			)
			return cleaned_queries

		merged: List[str] = []
		seen = set()
		for item in cleaned_queries + [str(q).strip() for q in generated if q and str(q).strip()]:
			key = item.lower()
			if key in seen or item.lower() == query.lower():
				continue
			seen.add(key)
			merged.append(item)

		return merged


def get_search_service(
	vdb_client: VectorDBInterface = Depends(get_vdb_client),
	embedding_client: LLMInterface = Depends(get_embedding_client),
	settings: Settings = Depends(get_settings),
	langchain_client: LCOpenAI = Depends(get_langchain_client),
) -> SearchService:
	return SearchService(
		vdb_client=vdb_client,
		embedding_client=embedding_client,
		settings=settings,
		langchain_client=langchain_client,
	)