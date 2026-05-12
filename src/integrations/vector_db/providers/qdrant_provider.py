
from qdrant_client import models, QdrantClient
from ..vdb_interface import VectorDBInterface
from typing import List, Optional, Dict, Any, Type
from helpers.logger import get_logger

logger = get_logger(__name__)


from .bm25 import BM25Encoder

class QdrantDBProvider(VectorDBInterface):

    def __init__(self,url: str,distance_method: str, vector_size: int):
        self.client: Optional[QdrantClient] = None
        self.url = url
        self.vector_size = vector_size
        self.distance_method = None
        if distance_method == "cosine":
            self.distance_method = models.Distance.COSINE
        elif distance_method == "dot":
            self.distance_method = models.Distance.DOT

        self.bm25_map: Dict[str, BM25Encoder] = {}
        
        

    def connect(self) -> None:
        self.client = QdrantClient(url=self.url)
        logger.info("[CONNECT SUCCESS]")

    def disconnect(self) -> None:
        self.client = None
        logger.info("[DISCONNECT] Client cleared")

    def fit_bm25(self, collection_name: str, texts: List[str]):
        bm25 = BM25Encoder()
        bm25.fit(texts)
        self.bm25_map[collection_name] = bm25
        logger.info(
            f"[BM25] Fitted for '{collection_name}' "
            f"with {len(texts)} documents, "
            f"vocab size: {len(bm25.vocab)}"
        )


    def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)

    def list_all_collections(self) -> List[str]:
        return [c.name for c in self.client.get_collections().collections]


    def _create_payload_indexes(
        self,
        collection_name: str,
        fields_for_indexing: List[Dict[str, Any]],
    ) -> None:
        if not fields_for_indexing:
            return
        if not self.is_collection_existed(collection_name):
            self.client.get_collection(collection_name=collection_name)

        for item in fields_for_indexing:
            field_name = item.get("name")
            field_type = item.get("type")
            if not field_name or field_type is None:
                continue

            resolved_field = self._resolve_field_path(field_name)
            schema = self._map_python_type_to_qdrant(field_type)

            self.client.create_payload_index(
                collection_name=collection_name,
                field_name=resolved_field,
                field_schema=schema,
            )


    def build_filter(self, filters: List[Dict[str, Any]]) -> Optional[models.Filter]:
        if not filters:
            return None

        conditions = []

        for item in filters:
            field = item.get("field")
            value = item.get("value")
            operator = item.get("op", "eq")  # default = equals

            if not field:
                continue

            key = self._resolve_field_path(field)

            if operator == "eq":
                match = models.MatchValue(value=value)

            elif operator == "in":
                match = models.MatchAny(any=value)

            elif operator == "range" and isinstance(value, dict):
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        range=models.Range(
                            gte=value.get("gte"),
                            lte=value.get("lte"),
                        ),
                    )
                )
                continue

            else:
                continue

            conditions.append(models.FieldCondition(key=key, match=match))

        if not conditions:
            return None

        return models.Filter(must=conditions)


    def _resolve_filters(self, filters: Optional[Any]) -> Optional[models.Filter]:
        if not filters:
            return None
        if isinstance(filters, list):
            return self.build_filter(filters)
        return filters



    
    def _map_python_type_to_qdrant(self, t: Type) -> models.PayloadSchemaType:
        if t == str:
            return models.PayloadSchemaType.KEYWORD
        elif t == int:
            return models.PayloadSchemaType.INTEGER
        elif t == float:
            return models.PayloadSchemaType.FLOAT
        elif t == bool:
            return models.PayloadSchemaType.BOOL
        else:
            raise ValueError(f"Unsupported index type: {t}")
    
    def _resolve_field_path(self, field: str) -> str:
        if field.startswith("metadata.") or field == "text":
            return field
        return f"metadata.{field}"

    def create_collection(
        self,
        collection_name: str,
        embedding_size: int,
        do_reset: bool = False,
        enable_bm25: bool = True,
        fields_for_indexing: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if do_reset and self.is_collection_existed(collection_name):
            self.delete_collection(collection_name)
            logger.info(f"Deleted collection {collection_name} for reset")

        created = False
        if not self.is_collection_existed(collection_name):
            create_payload = {
                "collection_name": collection_name,
                "vectors_config": models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method,
                ),
            }
            if enable_bm25:
                create_payload["sparse_vectors_config"] = {
                    "bm25": models.SparseVectorParams(),
                }
            self.client.create_collection(**create_payload)
            logger.info(f"Created collection {collection_name}")
            created = True

        if fields_for_indexing:
            self._create_payload_indexes(
                collection_name=collection_name,
                fields_for_indexing=fields_for_indexing,
            )

        return created

    async def ensure_collection_exists(
        self,
        collection_name: str,
        enable_bm25: bool ,
        fields_for_indexing: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not self.is_collection_existed(collection_name):
            self.create_collection(
                collection_name,
                embedding_size=self.vector_size,
                enable_bm25=enable_bm25,
                fields_for_indexing=fields_for_indexing,
            )
            logger.info(f"Created collection {collection_name}")

        return True

    def delete_collection(self, collection_name: str) -> None:
        self.bm25_map.pop(collection_name, None)
        self.client.delete_collection(collection_name=collection_name)
        return

    def delete_by_filter(
        self,
        collection_name: str,
        filters: Optional[Any] = None,
    ) -> Any:
        if not self.is_collection_existed(collection_name):
            logger.warning(
                "[DELETE BY FILTER] Collection does not exist",
                extra={"collection_name": collection_name},
            )
            return {"deleted": False, "reason": "collection_not_found"}

        resolved_filter = self._resolve_filters(filters)
        if resolved_filter is None:
            raise ValueError("delete_by_filter requires non-empty filters")

        result = self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(filter=resolved_filter),
        )
        return result

    def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)


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
        if not texts or not vectors or not metadatas:
            logger.warning("Skipping empty batch")
            return False
        if not (
            len(texts) == len(vectors)
            == len(metadatas) == len(record_ids)
        ):
            raise ValueError("Batch size mismatch")

        await self.ensure_collection_exists(
            collection_name=collection_name,
            enable_bm25=use_bm25,
            fields_for_indexing=fields_for_indexing
        )

        if use_bm25:
            self.fit_bm25(collection_name, texts)

        success = self._insert_many(
            collection_name=collection_name,
            texts=texts,
            vectors=vectors,
            record_ids=record_ids,
            metadata=metadatas,
            batch_size=batch_size,
            use_bm25=use_bm25,
        )

        if not success:
            raise RuntimeError(f"Failed to insert batch into {collection_name}")
        logger.info(
            f"Stored batch of {len(texts)} chunks in {collection_name}"
        )
        return True

    def _insert_many(
        self,
        collection_name: str,
        texts: list,
        vectors: list,
        record_ids: list,
        metadata: list = None,
        batch_size: int = 50,
        use_bm25: bool = True,
    ) -> bool:
        if metadata is None:
            metadata = [None] * len(texts)
        if not self.is_collection_existed(collection_name):
            self.client.get_collection(collection_name=collection_name)

        bm25 = self.bm25_map.get(collection_name) if use_bm25 else None

        for i in range(0, len(texts), batch_size):
            batch_points = []

            for j in range(i, min(i + batch_size, len(texts))):

               
                point_vector: Any = vectors[j]

                if bm25:
                    indices, values = bm25.encode(texts[j])
                    if indices and values:
                        point_vector = {
                            "": vectors[j],
                            "bm25": models.SparseVector(
                                indices=indices, values=values
                            )
                        }

                meta = metadata[j]
                if meta is not None and hasattr(meta, "dict"):
                    meta = meta.dict()
                elif meta is None:
                    meta = {}

                batch_points.append(
                    models.PointStruct(
                        id=record_ids[j],
                        vector=point_vector,
                        payload={
                            "text": texts[j],
                            "metadata": meta
                        }
                    )
                )

            self.client.upsert(
                collection_name=collection_name,
                points=batch_points,
            )

        return True

    def get_collection_chunks(
        self,
        collection_name: str,
        page: int = 1,
        limit: int = 10,
        text_limit: Optional[int] = 100,
        filters: Optional[Any] = None,
        with_vectors: bool = False,
    ) -> Dict[str, Any]:
        if page < 1:
            page = 1
        if not self.is_collection_existed(collection_name):
            self.client.get_collection(collection_name=collection_name)

        collection_info = self.client.get_collection(
            collection_name=collection_name
        )
        total_points = collection_info.points_count


        offset = None
        points = []

        for current_page in range(1, page + 1):
            scroll_kwargs = {
                "collection_name": collection_name,
                "limit": limit,
                "offset": offset,
                "with_payload": True,
                "with_vectors": with_vectors,
            }
            resolved_filters = self._resolve_filters(filters)
            
            if resolved_filters is not None:
                scroll_kwargs["scroll_filter"] = resolved_filters
                
            batch, next_offset = self.client.scroll(**scroll_kwargs)

            if current_page == page:
                points = batch
                break
            offset = next_offset
            if offset is None:
                points = []
                break

        chunks = []
        for p in points:
            payload = p.payload or {}
            text = payload.get("text", "")
            if text_limit and (len(text) > text_limit):
                text = text[:text_limit]
            chunk_item = {
                "id": str(p.id),
                "text": text,
                "metadata": payload.get("metadata", {}),
            }
            if with_vectors:
                chunk_item["vector"] = p.vector
            chunks.append(chunk_item)

        total_pages = (
            (total_points + limit - 1) // limit
            if total_points else 0
        )
        return {
            "collection_name": collection_name,
            "total_chunks": total_points,
            "page": page,
            "total_pages": total_pages,
            "returned_chunks": len(chunks),
            "chunks": chunks,
        }


    def search_by_vector(
        self,
        collection_name: str,
        vector: List[float],
        limit: int,
        filters: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        query_kwargs = {
            "collection_name": collection_name,
            "query": vector,
            "limit": limit,
            "with_payload": True,
        }
        resolved_filters = self._resolve_filters(filters)
        if resolved_filters is not None:
            query_kwargs["query_filter"] = resolved_filters

        results = self.client.query_points(**query_kwargs)
        return [
            {
                "id": str(p.id),
                "score": p.score,
                "text": (p.payload or {}).get("text", ""),
                "metadata": (p.payload or {}).get("metadata", {}),
            }
            for p in results.points
        ]
    
    
    async def search_by_keyword(
        self,
        collection_name: str,
        query_text: str,
        limit: int,
        filters: Optional[Any] = None,
        use_bm25: bool = True,
    ) -> List[Dict[str, Any]]:
        
        if not use_bm25:
            logger.info(f"[BM25] Disabled for collection: {collection_name}")
            return []

        logger.info(f"[BM25] collection: {collection_name} ")

        bm25 = self._ensure_bm25(collection_name)
        if not bm25:
            return []

        indices, values = bm25.encode(query_text)
        if not indices:
            logger.warning(f"[BM25] No matching terms for: '{query_text}'")
            return []

        query_kwargs = {
            "collection_name": collection_name,
            "query": models.SparseVector(indices=indices, values=values),
            "using": "bm25",
            "limit": limit,
            "with_payload": True,
        }
        resolved_filters = self._resolve_filters(filters)
        if resolved_filters is not None:
            query_kwargs["query_filter"] = resolved_filters

        results = self.client.query_points(**query_kwargs)
        return [
            {
                "id": str(p.id),
                "score": p.score,
                "text": (p.payload or {}).get("text", ""),
                "metadata": (p.payload or {}).get("metadata", {}),
            }
            for p in results.points
        ]
            
            
    def _rebuild_bm25_from_collection(self, collection_name: str) -> bool:

        logger.info(
            f"[BM25] Rebuilding for '{collection_name}' "
            f"from stored documents..."
        )
        all_texts = []
        offset = None
        while True:
            points, next_offset = self.client.scroll(
                collection_name=collection_name,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            for p in points:
                text = (p.payload or {}).get("text", "")
                if text:
                    all_texts.append(text)
            if next_offset is None:
                break
            offset = next_offset

        if not all_texts:
            logger.warning("[BM25] No texts found to fit")
            return False

        self.fit_bm25(collection_name, all_texts)
        return True

    def _ensure_bm25(self, collection_name: str) -> Optional[BM25Encoder]:

        bm25 = self.bm25_map.get(collection_name)
        if not bm25:
            if self._rebuild_bm25_from_collection(collection_name):
                bm25 = self.bm25_map.get(collection_name)
        return bm25