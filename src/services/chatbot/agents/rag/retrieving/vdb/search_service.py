from typing import Any, Dict, List, Optional

from core import Settings
from core.request_dependencies import (
	get_embedding_client,
	get_langchain_client,
	get_settings,
	get_vdb_client,
)
from fastapi import Depends
from helpers.logger import get_logger
from integrations.llm import LCOpenAI, LLMInterface
from integrations.vector_db import VectorDBInterface

from services.vdb_service.vdb_exceptions import VectorDBException
from services.vdb_service.vdb_exceptions import VectorizationError
from services.service_exceptions import ServiceException

from .query_rewriting_chain import build_query_rewriting_chain
from .reranker import Reranker
from .retrieval import Retrieval


logger = get_logger("chatbot_retrieval_search_service")


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
		query_text: Optional[str] = None,
	) -> List[Dict[str, Any]]:
		search_query = (query_text or str(field_value) or "").strip()
		return await self.search(
			collection_name=collection_name,
			query=search_query,
			limit=limit,
			filters=[{"field": field_name, "value": field_value, "op": "eq"}],
		)

	async def search_by_metadata_range(
		self,
		collection_name: str,
		field_name: str,
		gte: Any = None,
		lte: Any = None,
		limit: int = 10,
		query_text: Optional[str] = None,
	) -> List[Dict[str, Any]]:
		range_value: Dict[str, Any] = {}
		if gte is not None:
			range_value["gte"] = gte
		if lte is not None:
			range_value["lte"] = lte

		if not range_value:
			return []

		search_query = (query_text or f"{gte or ''} {lte or ''}").strip()
		return await self.search(
			collection_name=collection_name,
			query=search_query,
			limit=limit,
			filters=[{"field": field_name, "value": range_value, "op": "range"}],
		)

	async def search(
		self,
		collection_name: str,
		query: str,
		rewritten_queries: Optional[List[str]] = None,
		rewrite_mode: Optional[str] = None,
		limit: int = 10,
		filters: Optional[Any] = None,
	) -> List[Dict[str, Any]]:
		query = (query or "").strip()

		rewritten_queries = await self._resolve_rewritten_queries(
			query=query,
			rewrite_mode=rewrite_mode,
			rewritten_queries=rewritten_queries,
		)
		all_queries = [query] + [q for q in rewritten_queries if q and q.strip()]

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
			)

		if not candidates:
			return []

		final_top_k = max(1, int(limit or 10))

		cohere_key = self.settings.COHERE_API_KEY
		if not cohere_key:
			return candidates[:final_top_k]

		try:
			reranker = Reranker(api_key=cohere_key)
			reranked = await reranker.rerank(
				query=query,
				documents=candidates,
				top_k=final_top_k,
			)
			return reranked[:final_top_k]
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
			return candidates[:final_top_k]

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
				}
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