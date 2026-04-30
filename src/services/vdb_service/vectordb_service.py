from fastapi import Depends
from helpers.logger import get_logger
from integrations.integrations_dependencies import get_vdb_client
from integrations.vector_db import VectorDBInterface
from schemas.vectordb_schema import CollectionChunksResponse, ChunkResponse
from typing import Optional
import json
from models import ChunkMetadata


from .vdb_exceptions import (
    VectorDBException,

)
from ..service_exceptions import ProcessingError


logger = get_logger("vectordb_service")


class VDBService:

    def __init__(
        self,
        vdb_client: VectorDBInterface,

        
    ):
        self.vdb_client = vdb_client
        

        logger.info("Vector DB Push Service initialized")

    def get_collection_info(
        self,
        collection_name: str,
        project_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        try:
            info = self.vdb_client.get_collection_info(collection_name=collection_name)

            return json.loads(
                json.dumps(info, default=lambda x: x.__dict__)
            )

        except Exception as e:
            details = {
                "error": str(e),
                "type": type(e).__name__,
                "context": {
                    "project_id": project_id,
                    "tenant_id": tenant_id,
                    "collection_name": collection_name,
                }
            }
            logger.error("Failed to get collection info", extra=details)
            raise VectorDBException(details=details)

    def get_chunks(
        self,
        collection_name: str,
        page: int = 1,
        limit: int = 10,
        text_limit: Optional[int] = 100,
    ) -> CollectionChunksResponse:

        try:
            if page < 1:
                page = 1


            raw_data = self.vdb_client.get_collection_chunks(
                collection_name=collection_name,
                page=page,
                limit=limit,
                text_limit=text_limit
            )

            chunks = []
            for chunk_dict in raw_data["chunks"]:
                chunk = ChunkResponse(
                    id=chunk_dict["id"],
                    text=chunk_dict["text"],
                    metadata=chunk_dict["metadata"]
                )
                chunks.append(chunk)

            response = CollectionChunksResponse(
                collection_name=raw_data["collection_name"],
                total_chunks=raw_data["total_chunks"],
                page=raw_data["page"],
                total_pages=raw_data["total_pages"],
                returned_chunks=raw_data["returned_chunks"],
                chunks=chunks
            )

            return response

        except Exception as e:
            details = {
                "error": str(e),
                "type": type(e).__name__,
                "context": {
                    "collection_name": collection_name,
                    "page": page,
                    "limit": limit
                }
            }
            logger.error("Failed to get chunks", extra=details)
            raise ProcessingError(details=details)

    def delete_collection(
        self,
        collection_name: str,
        tenant_id: Optional[str] = None,
    ) -> dict:
        try:
            self.vdb_client.delete_collection(collection_name=collection_name)
            return {
                "collection_name": collection_name,
                "deleted": True,
            }
        except Exception as e:
            details = {
                "error": str(e),
                "type": type(e).__name__,
                "context": {
                    "tenant_id": tenant_id,
                    "collection_name": collection_name,
                },
            }
            logger.error("Failed to delete collection", extra=details)
            raise VectorDBException(details=details)


def get_vdb_service(
    vdb_client: VectorDBInterface = Depends(get_vdb_client),
) -> VDBService:
    return VDBService(vdb_client=vdb_client)

    