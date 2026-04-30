from pydantic import BaseModel,Field
from typing import List,Optional

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5

class ChunkResponse(BaseModel):
    id: str = Field(..., description="Chunk ID")
    text: str = Field(..., description="Chunk text (full or truncated)")
    metadata: dict


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