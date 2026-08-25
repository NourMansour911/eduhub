---
name: app-lifecycle-di
description: "Use when creating or modifying FastAPI app entry points, lifespan context managers, singleton service registration on app.state, or request-scoped dependency injection getters."
---

# App Lifecycle & Dependency Injection Skill

## Purpose

Defines the canonical patterns for FastAPI application startup, provider/service instantiation via the lifespan context manager, singleton registration on `app.state`, and request-scoped dependency getters. Grounded in `src/main.py` and the project's `src/core/` structure.

## When To Use

- Adding a new provider, repository, or service that must be available to all routes.
- Creating a new request dependency getter (`Depends()` target).
- Modifying the startup/shutdown sequence.
- Reviewing startup code for ordering issues or missing teardown.

---

## Rule 1: App Entry Point Structure

```python
# src/main.py — exact ordering matters

import os
import uvicorn
from core import get_settings
settings = get_settings()                          # Load settings FIRST

# Set global env vars BEFORE any LangChain imports
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"]    = settings.LANGSMITH_API_KEY
os.environ["LANGCHAIN_PROJECT"]    = settings.APP_NAME

from fastapi import FastAPI
from contextlib import asynccontextmanager
# ... all other imports after env setup ...

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup sequence (order matters) ---
    # 1. Register exception handler
    app.add_exception_handler(AppException, app_exception_handler)

    # 2. Instantiate infrastructure providers
    # 3. Connect/initialize each provider
    # 4. Instantiate repositories (Mongo bootstrap)
    # 5. Instantiate services (inject providers + repos)
    # 6. Instantiate orchestrators (inject services)

    yield

    # --- Shutdown sequence (reverse resource-heavy connections) ---
    app.state.vdb_client.disconnect()
    await app.state.redis_provider.disconnect()
    app.state.mongo_client.close()


app = FastAPI(lifespan=lifespan)
app.add_exception_handler(AppException, app_exception_handler)
app.include_router(...)
```

---

## Rule 2: Singleton Registration on `app.state`

Every singleton (provider, repo, service) is registered on `app.state` in the `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Providers ---
    vdb_factory          = VectorDBFactory(settings)
    app.state.vdb_client = vdb_factory.create(provider=settings.VECTOR_DB_BACKEND)
    app.state.vdb_client.connect()
    logger.info("VectorDB client loaded successfully")

    app.state.redis_provider = RedisProvider(settings.REDIS_URL)
    await app.state.redis_provider.connect()
    logger.info("Redis provider loaded successfully")

    # --- LLM clients ---
    llm_factory = LLMFactory()
    app.state.embedding_client = llm_factory.create(api_key="hf", provider=settings.EMBEDDING_BACKEND)
    app.state.embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID,
        embedding_size=settings.EMBEDDING_MODEL_SIZE,
    )
    app.state.langchain_client = LCOpenAI(api_key=settings.OPENAI_API_KEY, api_url=settings.OPENAI_API_URL)
    logger.info("LLM clients loaded successfully")

    # --- MongoDB ---
    app.state.mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
    app.state.mongo_db     = app.state.mongo_client[settings.MONGO_DB_NAME]
    mongo_repos = await init_mongo_resources(
        app.state.mongo_db,
        [AnswerRepo, LectureRepo, EvaluationRepo, StudentPersonaRepo],
    )
    app.state.lecture_repo         = mongo_repos["LectureRepo"]
    app.state.evaluation_repo      = mongo_repos["EvaluationRepo"]
    app.state.student_persona_repo = mongo_repos["StudentPersonaRepo"]
    logger.info("Mongo repositories loaded successfully")

    # --- Services ---
    app.state.vdb_service    = VDBService(vdb_client=app.state.vdb_client)
    app.state.lecture_service = LectureService(
        lecture_repo=app.state.lecture_repo,
        ...
    )
    # ... more services ...

    # --- Orchestrators (inject services, not providers directly) ---
    app.state.lecture_orchestrator = LectureOrchestrator(
        lecture_service=app.state.lecture_service,
        ...
    )

    yield

    # Teardown
    app.state.vdb_client.disconnect()
    await app.state.redis_provider.disconnect()
    app.state.mongo_client.close()
```

**Startup ordering rules:**
1. Infrastructure providers first (VDB, Redis, Mongo, LLM clients).
2. Repositories second (depend on DB clients).
3. Services third (depend on repos + providers).
4. Orchestrators last (depend on services).
- Every registered singleton MUST be logged with `logger.info` at creation.

---

## Rule 3: Request Dependency Getters

Request-scoped dependencies extract singletons from `app.state` via `Request`:

```python
# src/core/request_dependencies.py

from fastapi import Request

def get_lecture_service(request: Request):
    return request.app.state.lecture_service

def get_chatbot_service(request: Request):
    return request.app.state.chatbot_service

def get_redis_provider(request: Request):
    return request.app.state.redis_provider
```

**Usage in routers:**
```python
from fastapi import APIRouter, Depends
from core.request_dependencies import get_chatbot_service
from services.chatbot.chatbot_service import ChatbotService

router = APIRouter()

@router.post("/assistant/chat/{user_id}/{session_id}")
async def chat(
    user_id: str,
    session_id: str,
    payload: ChatRequest,
    chatbot_service: ChatbotService = Depends(get_chatbot_service),
):
    return await chatbot_service.chat(payload, user_id, session_id)
```

**Rules:**
- Dependency getters live in `src/core/request_dependencies.py`.
- Getters are synchronous functions returning `request.app.state.<attr>`.
- Routers MUST use `Depends(get_<service>)` — never `request.app.state` directly in route handlers.
- One getter per singleton — no multi-return getter functions.

---

## Rule 4: Settings Access

`Settings` is loaded once at module import time in `main.py`:

```python
# top of main.py — before any other imports
from core import get_settings
settings = get_settings()   # NOT cached with lru_cache
```

Services that need settings receive them as a constructor argument — they MUST NOT call `get_settings()` internally:

```python
# CORRECT — settings injected at construction
app.state.chatbot_service = ChatbotService(
    settings=settings,
    ...
)

# WRONG — service pulling settings itself
class ChatbotService:
    def __init__(self):
        self.settings = get_settings()  # ← Never do this
```

---

## Review Checklist

- Are global env vars (LangSmith, etc.) set before any LangChain imports?
- Are all singletons registered on `app.state` in the lifespan function?
- Is startup ordering: providers → repos → services → orchestrators?
- Is every registered singleton logged at creation?
- Are all dependency getters in `src/core/request_dependencies.py`?
- Do routers use `Depends(get_*)` rather than `request.app.state` directly?
- Does the lifespan `yield` before teardown? Is teardown in reverse connection order?
- Is `settings` injected into services as a constructor arg (not fetched internally)?
