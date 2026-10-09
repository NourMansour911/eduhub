---
name: ai-feature-service-pattern
description: "Use when creating or reviewing an AI-powered feature service (e.g., Chatbot, Summarize, Grading). Defines how to structure a feature service that owns an LLM graph, Redis session state, background tasks, and domain exception handling."
---

# AI Feature Service Pattern Skill

## Purpose

Defines the canonical structure for a domain service that wraps an AI workflow (LLM chain or LangGraph graph) and manages session state, background tasks, and domain exceptions. Grounded in `chatbot_service.py` as the primary reference.

## When To Use

- Building a new AI-powered feature service.
- Adding a new method to an existing AI service.
- Reviewing a service for correct layer boundaries.
- Deciding what belongs in the service vs. the graph vs. the router.

---

## Rule 1: Service Class Structure

```python
# src/services/<feature>/<feature>_service.py

class MyAIFeatureService:
    def __init__(
        self,
        lc_openai_client: LCOpenAI,
        settings: Settings,
        redis_provider: RedisProvider,
        some_repo: SomeRepo,
        some_integration_client: Any,
    ) -> None:
        # 1. Build internal tool wrappers (if any)
        self.my_tools = MyTools(some_integration_client)
        self.redis_provider = redis_provider
        self.some_repo      = some_repo

        # 2. Build llm_map — temperature decisions happen HERE, not in nodes
        llm_map = {
            "router":    lc_openai_client.get_langchain_llm(model=settings.GENERATION_MODEL_ID, temperature=0.0),
            "generator": lc_openai_client.get_langchain_llm(model=settings.GENERATION_MODEL_ID, temperature=0.7),
            "classifier": lc_openai_client.get_langchain_llm(model=settings.GENERATION_MODEL_ID, temperature=0.1),
        }

        # 3. Build graph (inject llm_map + dependencies)
        self.graph = build_my_feature_graph(
            llm_map=llm_map,
            redis_provider=redis_provider,
            tools=self.my_tools,
        )

        # 4. Build background chains
        self.summary_chain = build_summary_chain(llm_map["classifier"])

        # 5. Store config values needed at call time
        self.model_id = settings.GENERATION_MODEL_ID

    # --- Public API method (called by router) ---
    async def handle_request(self, payload: RequestDTO, user_id: str, session_id: str) -> ResponseDTO:
        # Validate business rules (NOT schema-level — Pydantic handles those)
        user_input = (payload.message or "").strip()
        if len(user_input) > 1000:
            raise MyFeatureValidationError(
                message=f"Input too long ({len(user_input)} chars). Max: 1000.",
                details={"length": len(user_input)},
            )

        # Load session state from Redis — fail fast if session missing
        collection = await self.redis_provider.get_collection(user_id=user_id, session_id=session_id)
        if collection is None:
            raise SessionNotFoundError(...)

        # Enrich graph input (Redis-first caching)
        cached_data = await self._get_and_cache_metadata(user_id, collection)

        # Prepare graph inputs (format/clip before invocation)
        last_messages = format_chat_history_for_graph(collection.messages, limit=6)

        # Invoke graph and measure latency
        _t0 = time.perf_counter()
        try:
            graph_result = await self.graph.ainvoke({
                "user_input":     user_input,
                "user_id":        user_id,
                "session_id":     session_id,
                "messages_history": last_messages,
                "cached_data":    cached_data,
            }, config={"run_name": "MyFeature Graph Run"})
        except Exception as exc:
            logger.exception("Graph invocation failed")
            raise MyFeatureProcessingError(
                message="Feature graph execution failed",
                details={"user_id": user_id, "error": str(exc)},
            ) from exc
        latency_ms = round((time.perf_counter() - _t0) * 1000, 2)

        # Extract result
        ai_reply = graph_result.get("response") or "Default fallback response."

        # Update and persist session DTO
        collection.messages.append({"role": "user",      "content": user_input})
        collection.messages.append({"role": "assistant", "content": ai_reply})
        await self.redis_provider.save_collection(collection, session_id=session_id)

        # Dispatch background tasks (fire-and-forget)
        asyncio.create_task(self._push_evaluation(
            user_input=user_input,
            answer=ai_reply,
            latency_ms=latency_ms,
            llm_usage_breakdown=graph_result.get("llm_usage_breakdown") or {},
            ...
        ))

        return ResponseDTO(result=ai_reply)

    # --- Private helpers (background, caching) ---
    async def _get_and_cache_metadata(self, user_id: str, collection) -> str: ...
    async def _push_evaluation(self, ...) -> None: ...        # fire-and-forget
```

---

## Rule 2: What Lives in the Service vs. the Graph

| Concern | Service | Graph/Node |
|---|---|---|
| Business validation (length checks, session guard) | ✅ | ❌ |
| Redis load/save | ✅ | ❌ |
| LLM temperature configuration (`llm_map`) | ✅ | ❌ |
| `asyncio.create_task` background dispatch | ✅ | ❌ |
| Latency measurement (`time.perf_counter`) | ✅ | ❌ |
| Message history clipping | ✅ (before `ainvoke`) | ❌ |
| Domain exception raising | ✅ | ❌ |
| LLM invocation + routing logic | ❌ | ✅ |
| Tool execution | ❌ | ✅ |
| State delta updates | ❌ | ✅ |

---

## Rule 3: Exception Handling in Services

```python
# Each AI feature service has its own exception file
# src/services/<feature>/<feature>_exceptions.py

from services.service_exceptions import ServiceException

class MyFeatureServiceException(ServiceException): ...

class MyFeatureValidationError(MyFeatureServiceException):
    def __init__(self, message="Validation failed", details=None):
        super().__init__(message=message, details=details, status_code=422, error_code="MYFEATURE_VALIDATION_ERROR")

class MyFeatureProcessingError(MyFeatureServiceException):
    def __init__(self, message="Processing failed", details=None):
        super().__init__(message=message, details=details, status_code=500, error_code="MYFEATURE_PROCESSING_ERROR")

class MyFeatureExternalError(MyFeatureServiceException):
    def __init__(self, message="External dependency failure", details=None):
        super().__init__(message=message, details=details, status_code=502, error_code="MYFEATURE_EXTERNAL_ERROR")
```

Exception handling pattern in service methods:
```python
try:
    graph_result = await self.graph.ainvoke(...)
except Exception as exc:
    logger.exception("Graph invocation failed")
    raise MyFeatureProcessingError(
        message="...",
        details={"error": str(exc)},
    ) from exc
```

---

## Rule 4: Constructor Injection Order

Always construct in this order:
1. Tool wrappers (wrap integration clients into callable tool objects).
2. LLM map (configure temperatures for each graph role).
3. Graph (pass llm_map + tools + providers).
4. Background chains (reuse LLMs from llm_map).
5. Config values needed at call time.

Never construct infrastructure clients inside the service — they must be injected.

---

## Review Checklist

- Does the service construct the `llm_map` with all temperature decisions?
- Does the service load/save Redis state (not the graph/nodes)?
- Is the graph invoked with `try/except` wrapping a domain-specific error?
- Are background tasks dispatched with `asyncio.create_task()` (not `await`)?
- Is latency measured around the full graph `ainvoke()` call?
- Is business validation done in the service (not duplicating Pydantic schema validation)?
- Does the service have its own `<feature>_exceptions.py`?
- Are all nodes' temperature configs set in the service's `llm_map`, not hardcoded in nodes?
