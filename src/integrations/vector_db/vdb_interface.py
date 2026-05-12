from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any,Type
class VectorDBInterface(ABC):

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    # Collections
    @abstractmethod
    def is_collection_existed(self, collection_name: str) -> bool:
        pass

    @abstractmethod
    def list_all_collections(self) -> List[str]:
        pass

    @abstractmethod
    def create_collection(
        self,
        collection_name: str,
        embedding_size: int,
        do_reset: bool = False,
        enable_bm25: bool = True,
        fields_for_indexing: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        pass

    @abstractmethod
    async def ensure_collection_exists(
        self,
        collection_name: str,
        enable_bm25: bool = True,
        fields_for_indexing: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        pass

    @abstractmethod
    def delete_by_filter(
        self,
        collection_name: str,
        filters: Optional[Any] = None,
    ) -> Any:
        pass

    @abstractmethod
    def get_collection_info(self, collection_name: str) -> dict:
        pass

    @abstractmethod
    async def store_batch(
        self,
        collection_name: str,
        batch_size: int,
        texts: List[str],
        vectors: List[List[float]],
        record_ids: List[str],
        metadatas: List[Dict[str, Any]],
        use_bm25: bool = True,
        fields_for_indexing: Optional[List[Dict[str, Type]]] = None,
    ) -> bool:
        pass

    @abstractmethod
    def get_collection_chunks(
        self,
        collection_name: str,
        page: int = 1,
        limit: int = 10,
        text_limit: Optional[int] = 100,
        filters: Optional[Any] = None,
        with_vectors: bool = False,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def search_by_vector(
        self,
        collection_name: str,
        vector: List[float],
        limit: int,
        filters: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def search_by_keyword(
        self,
        collection_name: str,
        query_text: str,
        limit: int,
        filters: Optional[Any] = None,
        use_bm25: bool = True
    ) -> List[Dict[str, Any]]:
        pass
