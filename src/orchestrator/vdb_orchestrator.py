from fastapi import Depends

from schemas.vectordb_schema import CollectionChunksResponse
from services.vdb_service import VDBService, get_vdb_service


class VDBOrchestrator:
    def __init__(self, vdb_service: VDBService):
        self.vdb_service = vdb_service

    def get_collection_info(self, collection_name: str):
        return self.vdb_service.get_collection_info(collection_name=collection_name)

    def get_chunks(
        self,
        collection_name: str,
        page: int,
        limit: int,
        text_limit: int,
    ) -> CollectionChunksResponse:
        return self.vdb_service.get_chunks(
            collection_name=collection_name,
            page=page,
            limit=limit,
            text_limit=text_limit,
        )

    def delete_collection(self, collection_name: str) -> dict:
        return self.vdb_service.delete_collection(collection_name=collection_name)


def get_vdb_orchestrator(
    vdb_service: VDBService = Depends(get_vdb_service),
) -> VDBOrchestrator:
    return VDBOrchestrator(vdb_service=vdb_service)
