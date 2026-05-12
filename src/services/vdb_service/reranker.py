from typing import List, Dict, Any
from helpers.logger import get_logger
import cohere

logger = get_logger(__name__)


class Reranker:
    def __init__(self, api_key: str, model: str = "rerank-english-v3.0"):
        self.client = cohere.AsyncClient(api_key)
        self.model = model

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int 
    ) -> List[Dict[str, Any]]:


        if not documents:
            return []

        query = (query or "").strip()
        if not query:
            return documents[:top_k]

        texts = [str(doc.get("text", "")) for doc in documents]
        doc_map = {i: doc for i, doc in enumerate(documents)}

        logger.info(f"Reranking {len(texts)} documents with Cohere...")

        response = await self.client.rerank(
            model=self.model,
            query=query,
            documents=texts,
            top_n=min(top_k, len(documents)),
        )

        reranked_docs = []
        for item in response.results:
            idx = item.index
            doc = doc_map[idx].copy()

            reranked_docs.append(
                {
                    "id": doc.get("id"),
                    "text": doc.get("text"),
                    "metadata": doc.get("metadata", {}),
                    "score": doc.get("score"),
                    "rerank_score": getattr(item, "relevance_score", None),
                }
            )

        return reranked_docs

