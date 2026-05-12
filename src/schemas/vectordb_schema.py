from pydantic import BaseModel, Field
from typing import List, Optional, Any

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5


class VDBSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User primary query")
    rewritten_queries: Optional[List[str]] = Field(
        default=None,
        description="Optional rewritten/expanded queries",
    )
    limit: int = Field(default=10, ge=1, le=100)
    filters: Optional[Any] = Field(
        default=None,
        description="Optional VDB filter list or native filter",
    )

class ChunkResponse(BaseModel):
    id: str = Field(..., description="Chunk ID")
    text: str = Field(..., description="Chunk text (full or truncated)")
    metadata: dict


class SearchChunkResponse(ChunkResponse):
    score: Optional[float] = None
    rerank_score: Optional[float] = None


class VDBSearchResponse(BaseModel):
    collection_name: str
    query: str
    returned_chunks: int
    chunks: List[SearchChunkResponse]


class CollectionChunksResponse(BaseModel):
    collection_name: str
    total_chunks: int
    page: int
    total_pages: int
    returned_chunks: int
    chunks: List[ChunkResponse]


class DeleteCollectionResponse(BaseModel):
    collection_name: str = Field(..., description="Vector collection name.")
    deleted: bool = Field(..., description="Indicates whether the collection was deleted.")
    
    
class ChunksQuerySchema(BaseModel):
    limit: Optional[int] = 10
    text_limit: Optional[int] = 100
    page: Optional[int] = 1