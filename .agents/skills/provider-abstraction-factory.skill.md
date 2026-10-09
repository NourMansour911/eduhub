---
name: provider-abstraction-factory
description: "Use when creating or extending integration providers for external systems (Vector DB, LLM, Redis, Document Intelligence). Defines the Abstract Base Class + Factory pattern for isolating vendor implementations."
---

# Provider Abstraction & Factory Skill

## Purpose

Defines the canonical pattern for integrating external vendors — abstract interface → concrete vendor implementation → factory class. Prevents vendor lock-in and keeps service code decoupled from SDK specifics. Grounded in `src/integrations/vector_db/` (interface + factory + Qdrant provider).

## When To Use

- Adding a new external vendor (new embedding model, new vector DB, new LLM provider).
- Reviewing integration code for abstraction boundary violations.
- Creating a new integration category (new type of external system).

---

## Rule 1: Directory Structure

```
src/integrations/
├── <category>/                       # e.g. vector_db, llm
│   ├── __init__.py                   # exports factory + interface
│   ├── <category>_interface.py       # Abstract base class
│   ├── <category>_factory.py         # Factory class
│   └── providers/
│       ├── __init__.py               # exports all providers
│       └── <vendor>_provider.py      # Concrete implementation
```

---

## Rule 2: The Abstract Interface

```python
# src/integrations/vector_db/vdb_interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type


class VectorDBInterface(ABC):
    """Abstract contract for all vector DB providers."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    async def is_collection_existed(self, collection_name: str) -> bool: ...

    @abstractmethod
    async def search_by_vector(
        self,
        collection_name: str,
        vector: List[float],
        limit: int,
        filters: Optional[Any] = None,
    ) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def search_by_keyword(
        self,
        collection_name: str,
        query_text: str,
        limit: int,
        filters: Optional[Any] = None,
    ) -> List[Dict[str, Any]]: ...

    # ... all other shared operations as @abstractmethod
```

**Rules:**
- Every method that ALL vendors must implement is `@abstractmethod`.
- No business logic, no SDK imports in the interface file.
- Return types use only standard Python types — never vendor-specific types.
- Method signatures are stable — changing them is a breaking change across all providers.

---

## Rule 3: The Vendor Implementation

```python
# src/integrations/vector_db/providers/qdrant_provider.py
from qdrant_client import QdrantClient        # vendor SDK import lives here only
from ..vdb_interface import VectorDBInterface


class QdrantDBProvider(VectorDBInterface):
    def __init__(self, url: str, vector_size: int, distance_method: str):
        self.url             = url
        self.vector_size     = vector_size
        self.distance_method = distance_method
        self.client: QdrantClient | None = None

    def connect(self) -> None:
        self.client = QdrantClient(url=self.url)

    def disconnect(self) -> None:
        if self.client:
            self.client.close()
        self.client = None

    async def search_by_vector(self, collection_name, vector, limit, filters=None):
        # Qdrant-specific implementation
        results = await self.client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=limit,
            query_filter=filters,
        )
        return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]
```

**Rules:**
- Vendor SDK imports are ONLY in the provider file — never in interface, factory, or service code.
- Return type matches the interface signature exactly (standard Python types).
- No business logic — translate vendor-specific results to standard dicts/lists.
- Constructor accepts config values (URLs, keys) — never reads from `os.environ` directly.

---

## Rule 4: The Factory

```python
# src/integrations/vector_db/vdb_factory.py
from .providers import QdrantDBProvider
from .vdb_interface import VectorDBInterface
from helpers.logger import get_logger
from core.settings import Settings

logger = get_logger(__name__)


class VectorDBFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create(self, provider: str) -> VectorDBInterface:
        if provider == "QDRANT":
            return QdrantDBProvider(
                distance_method=self.settings.VECTOR_DB_DISTANCE_METHOD,
                vector_size=self.settings.EMBEDDING_MODEL_SIZE,
                url=self.settings.QDRANT_URL,
            )
        raise ValueError(f"Unknown provider: {provider!r}")
```

**Rules:**
- Factory receives `Settings` as a constructor arg — not individual config values.
- Factory returns the interface type (`VectorDBInterface`), not the concrete type.
- Unknown provider strings should raise `ValueError` (not return `None`).
- Instantiation logic lives in the factory — not in `main.py`.
- Log provider selection at creation for observability.

---

## Rule 5: Service Layer Consumption

Services accept the interface type — never the concrete implementation:

```python
# CORRECT — typed against the interface
class VDBService:
    def __init__(self, vdb_client: VectorDBInterface):
        self.vdb_client = vdb_client

# WRONG — typed against the concrete class
class VDBService:
    def __init__(self, vdb_client: QdrantDBProvider):   # ← breaks on provider switch
        ...
```

---

## Rule 6: Adding a New Vendor

Steps to add a new vendor (e.g., `WeaviateDBProvider`):

1. Create `src/integrations/vector_db/providers/weaviate_provider.py` implementing `VectorDBInterface`.
2. Add `from .weaviate_provider import WeaviateDBProvider` to `providers/__init__.py`.
3. Add an `elif provider == "WEAVIATE":` branch to `VectorDBFactory.create()`.
4. Add `VECTOR_DB_BACKEND=WEAVIATE` to `.env.example` and `Settings`.
5. No changes needed in service code or routers.

---

## Review Checklist

- Does the new provider extend the abstract interface class?
- Are all vendor SDK imports confined to the provider file?
- Does the factory return the interface type, not the concrete type?
- Do services accept the interface type in their constructors?
- Does the factory raise on unknown providers (not return `None`)?
- Is the `Settings` object injected into the factory (not read from `os.environ`)?
