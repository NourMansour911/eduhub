from helpers.logger import get_logger
from integrations.llm import LLMInterface
from integrations.vector_db import VectorDBInterface
import asyncio
from typing import List, Dict, Any, Optional
import hashlib
from typing import List, Dict, Any
logger = get_logger(__name__, level="error")

from .vdb_exceptions import VectorizationError


class Retrieval:
    def __init__(self, embedding_client: LLMInterface,vdb_client: VectorDBInterface):
        self.embedding_client = embedding_client
        self.vdb_client = vdb_client
    
        
    async def retrieve_multi_query(
        self,
        queries: List[str],
        collection_name: str,
        top_k: int = 20,
        filters: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        queries = [q.strip() for q in (queries or []) if q and q.strip()]
        if not queries:
            return []

        per_query_k = max(1, (top_k + len(queries) - 1) // len(queries))
        tasks = [
            self._process_single_query(
                query=q,
                collection_name=collection_name,
                top_k=per_query_k,
                filters=filters,
            )
            for q in queries
        ]

        all_results = await asyncio.gather(*tasks)


        return self._reciprocal_rank_fusion_across_lists(all_results, top_k=top_k)
    
    async def _process_single_query(
        self,
        query: str,
        collection_name: str,
        top_k: int,
        filters: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        try:
            emb = await self.embedding_client.embed_text(query)
        except Exception as e:
            raise VectorizationError(details={"query": query, "error": str(e), "type": type(e).__name__})

        semantic_task = asyncio.to_thread(
            self.vdb_client.search_by_vector,
            collection_name,
            emb[0],
            top_k,
            filters,
        )

        keyword_task = self.vdb_client.search_by_keyword(
            collection_name=collection_name,
            query_text=query,
            limit=top_k,
            filters=filters,
        )

        semantic_results, keyword_results = await asyncio.gather(semantic_task, keyword_task)
        semantic_results = self._deduplicate_by_text(semantic_results)
        keyword_results = self._deduplicate_by_text(keyword_results)

        logger.info(f"Retrieved {len(semantic_results)} semantic results and {len(keyword_results)} keyword results for query: {query}")
        fused = self._reciprocal_rank_fusion([
            semantic_results,
            keyword_results,
            
        ],top_k = top_k)

        return fused

    def _reciprocal_rank_fusion(self, result_lists: List[List[Dict[str, Any]]], top_k: int) -> List[Dict[str, Any]]:
        fused_scores: Dict[str, Dict[str, Any]] = {}

        weights = [0.7, 0.3]  

        for weight, results in zip(weights, result_lists):
            for rank, item in enumerate(results, start=1):
                doc_id = str(item.get("id"))
                if not doc_id or doc_id == "None":
                    continue

                score = weight * (1 / (60 + rank))

                if doc_id not in fused_scores:
                    fused_scores[doc_id] = {
                        "rrf_score": 0,
                        "doc": item
                    }

                fused_scores[doc_id]["rrf_score"] += score

        reranked = sorted(
            fused_scores.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )

        return [item["doc"] for item in reranked[:top_k]]

    def _reciprocal_rank_fusion_across_lists(
        self,
        result_lists: List[List[Dict[str, Any]]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        fused_scores: Dict[str, float] = {}
        docs_by_id: Dict[str, Dict[str, Any]] = {}

        for results in result_lists:
            for rank, item in enumerate(results or [], start=1):
                doc_id = str(item.get("id"))
                if not doc_id or doc_id == "None":
                    continue
                docs_by_id.setdefault(doc_id, item)
                fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + (1 / (60 + rank))

        ordered_ids = sorted(fused_scores.keys(), key=lambda i: fused_scores[i], reverse=True)
        return [docs_by_id[i] for i in ordered_ids[:top_k]]
    


    def _deduplicate_by_text(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        seen = set()
        cleaned = []

        for item in results or []:
            text = (item.get("text") or "").strip()
            if not text:
                continue

            text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

            if text_hash in seen:
                continue

            seen.add(text_hash)
            cleaned.append(item)

        return cleaned