from schemas.vectordb_schema import VDBSearchRequest, VDBSearchResponse, SearchChunkResponse
from fastapi import Depends
from helpers.logger import get_logger
from integrations.vector_db import VectorDBInterface
from schemas.vectordb_schema import CollectionChunksResponse, ChunkResponse
from typing import Optional, List, Dict, Type, Any
from core.request_dependencies import get_vdb_client, get_embedding_client
from integrations.llm import LLMInterface
from core import Settings, get_settings
from .retrieval import Retrieval
from .reranker import Reranker
import json



from .vdb_exceptions import (
    VectorDBException,

)
from ..service_exceptions import ProcessingError
from ..service_exceptions import ServiceException


logger = get_logger("vectordb_service")


class VDBService:

    def __init__(
        self,
        vdb_client: VectorDBInterface,
        embedding_client: LLMInterface,
        settings: Settings,
    ):
        self.vdb_client = vdb_client
        self.embedding_client = embedding_client
        self.settings = settings
        

        logger.info("Vector DB Push Service initialized")

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
        limit: int = 10,
        filters: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:


        query = (query or "").strip()

        rewritten_queries = rewritten_queries or []
        all_queries = [query] + [q for q in rewritten_queries if q and q.strip()]


        base_k = max(1, limit)
        candidate_k = min((base_k * 4), 50)

        try:
            retrieval = Retrieval(embedding_client=self.embedding_client, vdb_client=self.vdb_client)
            candidates = await retrieval.retrieve_multi_query(
                queries=all_queries,
                collection_name=collection_name,
                top_k=candidate_k,
                filters=filters,
            )
        except ServiceException:
            raise
        except Exception as e:
            raise VectorDBException(
                details={
                    "operation": "retrieve_multi_query",
                    "collection_name": collection_name,
                    "error": str(e),
                    "type": type(e).__name__,
                }
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
        except Exception as e:
            logger.warning(
                "Rerank failed; falling back to retrieval results",
                extra={
                    "operation": "search.rerank",
                    "collection_name": collection_name,
                    "error": str(e),
                    "type": type(e).__name__,
                },
            )
            return candidates[:final_top_k]

    async def search_api(
        self,
        collection_name: str,
        body: VDBSearchRequest,
    ) -> VDBSearchResponse:
        try:
            results = await self.search(
                collection_name=collection_name,
                query=body.query,
                rewritten_queries=body.rewritten_queries,
                limit=body.limit,
                filters=body.filters,
            )

            chunks = [
                SearchChunkResponse(
                    id=str(item.get("id")),
                    text=item.get("text", ""),
                    metadata=item.get("metadata", {}) or {},
                    score=item.get("score"),
                    rerank_score=item.get("rerank_score"),
                )
                for item in (results or [])
            ]

            return VDBSearchResponse(
                collection_name=collection_name,
                query=body.query,
                returned_chunks=len(chunks),
                chunks=chunks,
            )
        except ServiceException:
            raise
        except Exception as e:
            raise VectorDBException(
                details={
                    "operation": "search_api",
                    "collection_name": collection_name,
                    "error": str(e),
                    "type": type(e).__name__,
                }
            )

    def get_collection_info(
        self,
        collection_name: str,
    ):
        try:
            info = self.vdb_client.get_collection_info(collection_name=collection_name)

            return json.loads(
                json.dumps(info, default=lambda x: x.__dict__)
            )

        except Exception as e:
            raise VectorDBException(
                details={
                    "operation": "get_collection_info",
                    "collection_name": collection_name,
                    "error": str(e),
                    "type": type(e).__name__,
                }
            )

    def get_chunks(
        self,
        collection_name: str,
        text_limit: int,
        page: int ,
        limit: int ,
    ) -> CollectionChunksResponse:

        try:
            if page < 1:
                page = 1

            raw_data = self.vdb_client.get_collection_chunks(
                collection_name=collection_name,
                page=page,
                limit=limit,
                text_limit=text_limit,
            )

            chunks = []
            for chunk_dict in raw_data["chunks"]:
                chunk = ChunkResponse(
                    id=chunk_dict["id"],
                    text=chunk_dict["text"],
                    metadata=chunk_dict["metadata"],
                )
                chunks.append(chunk)

            response = CollectionChunksResponse(
                collection_name=raw_data["collection_name"],
                total_chunks=raw_data["total_chunks"],
                page=raw_data["page"],
                total_pages=raw_data["total_pages"],
                returned_chunks=raw_data["returned_chunks"],
                chunks=chunks,
            )

            return response

        except Exception as e:
            raise ProcessingError(
                details={
                    "operation": "get_chunks",
                    "collection_name": collection_name,
                    "page": page,
                    "limit": limit,
                    "error": str(e),
                    "type": type(e).__name__,
                }
            )

    def delete_collection(
        self,
        collection_name: str,
    ) -> dict:
        try:
            self.vdb_client.delete_collection(collection_name=collection_name)
            return {
                "collection_name": collection_name,
                "deleted": True,
            }
        except Exception as e:
            raise VectorDBException(
                details={
                    "operation": "delete_collection",
                    "collection_name": collection_name,
                    "error": str(e),
                    "type": type(e).__name__,
                }
            )

    def delete_by_filter(
        self,
        collection_name: str,
        filters: Optional[object] = None,
    ) -> dict:
        try:
            result = self.vdb_client.delete_by_filter(
                collection_name=collection_name,
                filters=filters,
            )
            return {
                "collection_name": collection_name,
                "deleted": True,
                "result": json.loads(json.dumps(result, default=lambda x: x.__dict__)),
            }
        except Exception as e:
            raise VectorDBException(
                details={
                    "operation": "delete_by_filter",
                    "collection_name": collection_name,
                    "filters": filters,
                    "error": str(e),
                    "type": type(e).__name__,
                }
            )

    async def store_batch(
        self,
        collection_name: str,
        batch_size: int,
        texts: List[str],
        vectors: List[List[float]],
        record_ids: List[str],
        metadatas: List[dict],
        use_bm25: bool = True,
        fields_for_indexing: Optional[List[Dict[str, Type]]] = None,
    ) -> bool:
        try:
            return await self.vdb_client.store_batch(
                collection_name=collection_name,
                batch_size=batch_size,
                texts=texts,
                vectors=vectors,
                record_ids=record_ids,
                metadatas=metadatas,
                use_bm25=use_bm25,
                fields_for_indexing=fields_for_indexing,
            )
        except Exception as e:
            raise VectorDBException(
                details={
                    "operation": "store_batch",
                    "collection_name": collection_name,
                    "batch_size": batch_size,
                    "texts_count": len(texts) if texts is not None else None,
                    "vectors_count": len(vectors) if vectors is not None else None,
                    "error": str(e),
                    "type": type(e).__name__,
                }
            )


def get_vdb_service(
    vdb_client: VectorDBInterface = Depends(get_vdb_client),
    embedding_client: LLMInterface = Depends(get_embedding_client),
    settings: Settings = Depends(get_settings),
) -> VDBService:
    return VDBService(vdb_client=vdb_client, embedding_client=embedding_client, settings=settings)

    