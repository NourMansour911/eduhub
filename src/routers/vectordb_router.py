from fastapi import APIRouter, Depends, Path

from helpers import get_logger
from orchestrator import VDBOrchestrator, get_vdb_orchestrator
from schemas.vectordb_schema import CollectionChunksResponse, ChunksQuerySchema, DeleteCollectionResponse

logger = get_logger(__name__)

vectordb_route = APIRouter(
    prefix="/vdb/{collection_name}",
    tags=["VectorDB"],
)


@vectordb_route.get(
    "/info",
    summary="Get collection info",
    description="Returns the underlying vector collection information.",
    response_description="Collection metadata and info payload.",
)
async def get_collection_info(
    collection_name: str = Path(..., description="Vector collection name."),
    orchestrator: VDBOrchestrator = Depends(get_vdb_orchestrator),
):
    return orchestrator.get_collection_info(collection_name=collection_name)


@vectordb_route.get(
    "/chunks",
    response_model=CollectionChunksResponse,
    summary="List collection chunks",
    description="Returns paginated chunks from the vector collection.",
    response_description="Paginated chunk list.",
)
async def get_collection_chunks(
    collection_name: str = Path(..., description="Vector collection name."),
    query: ChunksQuerySchema = Depends(),
    orchestrator: VDBOrchestrator = Depends(get_vdb_orchestrator),
):
    return orchestrator.get_chunks(
        collection_name=collection_name,
        page=query.page,
        limit=query.limit,
        text_limit=query.text_limit,
    )


@vectordb_route.delete(
    "",
    response_model=DeleteCollectionResponse,
    summary="Delete collection",
    description="Deletes the vector collection and its stored chunks.",
    response_description="Deletion result payload.",
)
async def delete_collection(
    collection_name: str = Path(..., description="Vector collection name."),
    orchestrator: VDBOrchestrator = Depends(get_vdb_orchestrator),
):
    return orchestrator.delete_collection(collection_name=collection_name)
