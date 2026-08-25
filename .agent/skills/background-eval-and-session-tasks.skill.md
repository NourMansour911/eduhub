---
name: background-eval-and-session-tasks
description: "Use when adding fire-and-forget background tasks, evaluation pipelines, or thresholded background chain execution in any feature service."
---

# Background Evaluation & Session Tasks Skill

## Purpose

Defines the canonical patterns for launching non-blocking background tasks after returning an HTTP response — including the 4-layer evaluation telemetry model and thresholded session state update chains. Grounded in `chatbot_service.py`.

## When To Use

- Adding a fire-and-forget operation after a service call (evaluation, analytics, state sync).
- Implementing a background chain that should not block the HTTP response.
- Building an evaluation/telemetry pipeline that writes to MongoDB asynchronously.
- Adding thresholded background triggers (e.g., "run every N turns").

---

## Pattern 1: Fire-and-Forget with `asyncio.create_task`

```python
import asyncio

async def handle_request(self, ...) -> ResponseDTO:
    # 1. Main path — do the core work and get the result
    result = await self._do_core_work(...)

    # 2. Dispatch background tasks AFTER the result is ready — BEFORE returning
    asyncio.create_task(self._push_evaluation(
        query=query,
        answer=result.answer,
        latency_ms=latency_ms,
        ...
    ))

    asyncio.create_task(self._update_session_background(
        ...
    ))

    # 3. Return immediately — background tasks run independently
    return result
```

**Rules:**
- Use `asyncio.create_task()` — NOT `await`. `await` blocks the response.
- Dispatch background tasks AFTER the result object is fully assembled.
- Do NOT `await asyncio.gather(main_task, background_task)` — this defeats the purpose.
- Background tasks MUST be `async def` methods on the service class.
- Background tasks MUST catch all exceptions internally — a crash in a background task must never surface to the caller.

```python
async def _push_evaluation(self, ...) -> None:
    try:
        # ... write to MongoDB ...
    except Exception as exc:
        logger.warning("Failed to push evaluation: %s", exc)
        # Swallow — never re-raise in a background task
```

---

## Pattern 2: The 4-Layer Evaluation Model

After every AI-assisted response, construct and persist an `EvaluationModel` document with four structured layers:

```python
from models import EvaluationModel
from models.evaluation_model import RequestLayer, RetrievalLayer, GenerationLayer, PerformanceLayer

async def _push_evaluation(
    self,
    user_query: str,
    context: str,
    answer: str,
    student_id: str,
    session_id: str,
    run_step_outputs: list,
    persona: str,
    summary: str,
    llm_usage_breakdown: dict,
    latency_ms: float,
) -> None:
    try:
        doc = EvaluationModel(
            request=RequestLayer(
                user_query=user_query,
                session_id=session_id,
                student_id=student_id,
                context_data={"persona": persona, "summary": summary},
            ),
            retrieval=RetrievalLayer(
                final_context=context,
                raw_documents=[
                    s.model_dump() if hasattr(s, "model_dump") else s
                    for s in (run_step_outputs or [])
                ],
            ),
            generation=GenerationLayer(
                final_answer=answer,
            ),
            performance=PerformanceLayer(
                latency_ms=latency_ms,
                token_usage=llm_usage_breakdown or {},
            ),
        )
        await self.evaluation_repo.add_eval_session(doc)
        logger.info("Evaluation session pushed to MongoDB.")
    except Exception as exc:
        logger.warning("Failed to push evaluation session to MongoDB: %s", exc)
```

**Layer Responsibilities:**

| Layer | Fields | Purpose |
|---|---|---|
| `RequestLayer` | `user_query`, `session_id`, `student_id`, `context_data` | What the user asked and their session context |
| `RetrievalLayer` | `final_context` (formatted string), `raw_documents` (raw `StepOutput` list) | What was retrieved from the DB |
| `GenerationLayer` | `final_answer`, `parameters`, `metadata` | What the LLM produced |
| `PerformanceLayer` | `latency_ms`, `token_usage` (hierarchical breakdown) | Latency and token cost |

**Rules:**
- Latency is wall-clock time from graph invocation start to result availability: `latency_ms = round((time.perf_counter() - _t0) * 1000, 2)`.
- `token_usage` is the full hierarchical `llm_usage_breakdown` dict — not a flat sum.
- `raw_documents` serializes `StepOutput` objects via `.model_dump()`.

---

## Pattern 3: Thresholded Background Chain Execution

Background chains (summary, persona update) should not run on every turn. Apply a **message count threshold**:

```python
# In the service layer:

# 1. Track unsummarized message count in session state (Redis DTO)
if needs_summary_update:
    collection.unsummarized_count += 2   # +2 per turn (user + assistant)

# 2. Trigger summary chain only when threshold is met
should_run_summary_now = needs_summary_update and collection.unsummarized_count >= 6

# 3. Dispatch background tasks conditionally
if needs_persona_update or should_run_summary_now:
    asyncio.create_task(self._update_persona_and_summary_background(
        run_persona=needs_persona_update,
        run_summary=should_run_summary_now,
        ...
    ))
```

**Threshold Convention:**
- Summary chain threshold: **6 messages** (3 turns) — reduces summarization calls by up to 83%.
- Reset `unsummarized_count` to `0` after the summary chain completes successfully.

---

## Pattern 4: Parallel Background Chain Execution

When multiple background chains may run simultaneously, use `asyncio.gather` inside the background task:

```python
async def _update_persona_and_summary_background(
    self, run_persona: bool, run_summary: bool, ...
) -> None:
    try:
        tasks = []
        tasks.append(
            self.summary_chain.ainvoke({...})
            if run_summary else asyncio.sleep(0)
        )
        tasks.append(
            self.persona_chain.ainvoke({...})
            if run_persona else asyncio.sleep(0)
        )

        new_summary, persona_decision = await asyncio.gather(*tasks)

        # Re-fetch from Redis (state may have changed while we were running)
        collection = await self.redis_provider.get_collection(
            user_id=student_id, session_id=session_id
        )
        if collection:
            if run_summary and new_summary:
                collection.summary            = new_summary
                collection.unsummarized_count = 0
            if run_persona and persona_decision and persona_decision.should_update:
                collection.persona = persona_decision.updated_persona
            await self.redis_provider.save_collection(collection, session_id=session_id)
    except Exception as exc:
        logger.error("Background update failed: %s", exc, exc_info=True)
```

**Rules:**
- Always use `asyncio.sleep(0)` as a no-op placeholder to keep `gather` symmetric.
- Re-fetch from Redis inside the background task — the main request may have already written newer state.
- Background task must save updated collection back to Redis after changes.

---

## Latency Measurement Convention

```python
import time

_t0 = time.perf_counter()
result = await self.graph.ainvoke({...})
latency_ms = round((time.perf_counter() - _t0) * 1000, 2)
```

Always measure the **full graph invocation** wall-clock time, not individual node times. Node-level timing uses `log_duration` context manager from `utils.py`.

---

## Review Checklist

- Are background tasks dispatched with `asyncio.create_task()`, not `await`?
- Do background tasks catch all exceptions and log (not re-raise)?
- Does the evaluation model include all 4 layers?
- Is latency measured as wall-clock time around the full graph invocation?
- Is `token_usage` the full hierarchical breakdown (not a flat total)?
- Does summary chain use a threshold count (not triggered every turn)?
- Is Redis re-fetched inside the background task before writing?
