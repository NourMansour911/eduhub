---
name: redis-session-state-lifecycle
description: "Use when implementing session state management with Redis, including session start/chat/end lifecycle, Redis-first caching with DB fallback, and RedisSessionDTO operations."
---

# Redis Session State Lifecycle Skill

## Purpose

Defines the canonical pattern for managing AI session state through a `RedisSessionDTO` stored in Redis, including the session start → chat → end lifecycle and the Redis-first caching strategy for user metadata. Grounded in `chatbot_service.py` and `redis_provider.py`.

## When To Use

- Creating a new stateful AI session handler.
- Adding Redis-backed session state to a service.
- Implementing a "Redis-first, DB fallback" caching pattern.
- Building session start/end endpoints.

---

## Rule 1: The Redis Session DTO

Session state is stored as a single JSON-serialized Pydantic model keyed by `user:{user_id}:session:{session_id}`:

```python
# dtos/redis_session_dto.py
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class RedisSessionDTO(BaseModel):
    user_id:            str
    messages:           List[Dict[str, Any]]  = Field(default_factory=list)
    persona:            Optional[str]          = None
    summary:            Optional[str]          = None
    student_courses:    Optional[str]          = None      # cached from SQL
    contexts:           List[List[Any]]        = Field(default_factory=list)  # per-turn StepOutputs
    unsummarized_count: int                    = 0
```

**Field conventions:**
- `messages`: full `[{role, content}]` history — stored at full length in Redis, clipped when passed to graphs.
- `persona`: loaded from MongoDB at session start, updated in background tasks.
- `summary`: rolling summary updated by background chain when `unsummarized_count >= 6`.
- `student_courses`: cached once from SQL on first chat turn, reused for session lifetime.
- `contexts`: `List[List[StepOutput]]` — one inner list per chat turn (last 3 turns used for cross-turn context injection).
- `unsummarized_count`: incremented by 2 per meaningful turn; reset to 0 after summary chain runs.

---

## Rule 2: Redis Key Schema

```python
def build_collection_key(self, user_id: str, session_id: str) -> str:
    return f"user:{user_id}:session:{session_id}"
```

All Redis operations for session state go through `get_collection` / `save_collection` on `RedisProvider`. Never construct the key manually in service code.

---

## Rule 3: Redis-First Caching Pattern

For data that is expensive to fetch but stable per session (e.g., enrolled courses), apply a **Redis-first, SQL fallback** pattern:

```python
async def _get_and_cache_student_courses(
    self, student_id: str, collection: RedisSessionDTO
) -> str:
    # 1. Redis hit — use cached value immediately
    if collection.student_courses:
        logger.info("Using cached student_courses from Redis: %s", collection.student_courses)
        return collection.student_courses

    # 2. Redis miss — fetch from authoritative source
    logger.info("student_courses not found in Redis, fetching from SQL for: %s", student_id)
    try:
        courses     = await self.sql_tools.get_student_courses(student_id)
        courses_str = format_student_courses(courses)
    except Exception as exc:
        logger.warning("Failed to retrieve student courses. Falling back to placeholder. %s", exc)
        courses_str = "Information temporarily unavailable"

    # 3. Write back to DTO (caller saves DTO to Redis after this)
    collection.student_courses = courses_str
    return courses_str
```

**Rules:**
- Always check the DTO field first — never hit the DB if it's already cached.
- Write the fetched value into the DTO so the caller persists it.
- On fetch failure, use a graceful fallback string — never raise from this helper.

---

## Rule 4: Session Lifecycle

### Session Start (`POST /session/start`)

```python
# Load persona from MongoDB → write initial DTO to Redis
async def start_session(self, student_id: str, session_id: str) -> None:
    persona_doc = await self.student_persona_repo.get_persona_by_student_id(student_id)
    persona_str = persona_doc.persona if persona_doc else None

    collection = RedisSessionDTO(
        user_id=student_id,
        persona=persona_str,
    )
    await self.redis_provider.save_collection(collection, session_id=session_id)
    logger.info("Session started. student_id: %s | session_id: %s", student_id, session_id)
```

### Chat Turn (`POST /assistant/chat`)

```python
# Full turn flow in service layer:
async def chat(self, payload, student_id, session_id):
    # 1. Load from Redis — fail fast if session not found
    collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
    if collection is None:
        raise SessionNotFoundError(...)

    # 2. Enrich state (Redis-first caching)
    student_courses = await self._get_and_cache_student_courses(student_id, collection)
    last_messages   = format_chat_history_for_graph(collection.messages, limit=6)

    # 3. Invoke graph
    graph_result = await self.chatbot_graph.ainvoke({
        "user_query":       user_query,
        "student_id":       student_id,
        "session_id":       session_id,
        "student_courses":  student_courses,
        "messages_history": last_messages,
        "user_persona":     collection.persona,
        "session_summary":  collection.summary,
    })

    # 4. Update DTO
    collection.messages.append({"role": "user",      "content": user_query})
    collection.messages.append({"role": "assistant", "content": ai_reply})
    if run_step_outputs:
        collection.contexts.append(run_step_outputs)

    # 5. Persist updated DTO
    await self.redis_provider.save_collection(collection, session_id=session_id)

    # 6. Dispatch background tasks (do NOT await)
    asyncio.create_task(self._push_evaluation(...))
    asyncio.create_task(self._update_persona_and_summary_background(...))

    return response_obj
```

### Session End (`POST /session/end`)

```python
# Archive to vector DB → upsert persona to MongoDB → clear Redis
async def end_session(self, student_id: str, session_id: str) -> None:
    collection = await self.redis_provider.get_collection(user_id=student_id, session_id=session_id)
    if collection is None:
        raise SessionNotFoundError(...)

    # Archive session summary to vector DB (for future cross-session retrieval)
    if collection.summary:
        await self.vdb_service.store_session_history(...)

    # Upsert final persona to MongoDB
    if collection.persona:
        await self.student_persona_repo.upsert_persona(student_id, collection.persona)

    # Clear Redis
    await self.redis_provider.clear_session_collection(user_id=student_id, session_id=session_id)
    logger.info("Session ended. student_id: %s | session_id: %s", student_id, session_id)
```

---

## Rule 5: DTO Persistence Timing

| When | Action |
|---|---|
| Session start | Write initial DTO with `persona` |
| After graph result | Update `messages`, `contexts`, then `save_collection` |
| Background persona update | Re-fetch → mutate `persona` → `save_collection` |
| Background summary update | Re-fetch → mutate `summary`, reset `unsummarized_count` → `save_collection` |
| Session end | `clear_session_collection` |

**Critical rule:** Background tasks MUST **re-fetch** from Redis before writing — the main request may have already saved a newer version while the background task was running.

---

## Review Checklist

- Is session state stored as a `RedisSessionDTO` (not raw dicts)?
- Is the Redis key built through `build_collection_key`, not constructed manually?
- Is enrolled courses fetched with Redis-first caching (check DTO first)?
- Does the chat handler load, mutate, then save the DTO — never partial updates?
- Do background tasks re-fetch from Redis before writing?
- Is session cleanup done via `clear_session_collection` at session end?
- Is `SessionNotFoundError` raised (not a generic error) when Redis returns `None`?
