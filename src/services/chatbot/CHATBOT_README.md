# Chatbot Service

> A stateful, adaptive AI tutoring assistant — built as a two-level LangGraph system that orchestrates session memory, student persona, and an Agentic RAG subgraph.

**Entry point:** `chatbot_service.py` → `ChatbotService.chat()`

---

## Architecture Overview

The Chatbot Service exposes a single `chat()` method which is the primary handler for `POST /assistant/chat/{user_id}/{session_id}`. It orchestrates the full lifecycle: loading session state from Redis, invoking the chatbot graph, persisting updates, and firing off background tasks for evaluation and persona/summary updates.

### Why Cyclic DAG Over `bind_tools`?

The conventional LangChain agent pattern (`bind_tools`) operates as a loop where the LLM selects **one tool at a time**, reads its result, then decides the next tool. For a tutoring system that may need to resolve a lecture name → fetch content → simultaneously search session history, this means **N tools = N sequential LLM calls**.

This service replaces that pattern with a **Cyclic DAG architecture**:

- The **Planner** (one LLM call) emits a complete typed execution plan — a list of steps with explicit `depends_on` relationships.
- The **Executor** (no LLM) runs all dependency-satisfied steps **in parallel** via `asyncio.gather`.
- The **Reflection** node evaluates the results and triggers a targeted replan if needed — instead of silently returning empty results.

The practical effect: a query requiring 3 independent tool calls costs **1 LLM call + 3 parallel async I/O calls** instead of 3 sequential LLM + tool round trips. Tool results stay in the executor's state dictionary and are never re-tokenized through the LLM mid-execution.

### Two-Level Graph Structure

The service is built as two nested LangGraph graphs:

```
HTTP POST /assistant/chat/{user_id}/{session_id}
  │
  ▼
ChatbotService.chat()
  ├── Input validation (query length ≤ 1000 chars, student_id, session_id)
  ├── Load RedisSessionDTO (messages, persona, summary, contexts, courses)
  ├── Cache/fetch student_courses from SQL (Redis-first, SQL fallback)
  ├── Deduplicate last 3 turns of tool outputs from Redis contexts
  ├── Invoke chatbot_graph.ainvoke(...)
  │     │
  │     ▼
  │   [Orchestrator] ── route_to_rag ──► [RAG Node] ──► [Answering (Luma)]
  │         └──────── direct_answer ────────────────► [Answering (Luma)]
  │
  ├── Append user/assistant messages to Redis
  ├── Persist run_step_outputs to Redis contexts
  ├── Save RedisSessionDTO back to Redis
  ├── asyncio.create_task → _push_evaluation() [fire-and-forget → MongoDB]
  └── asyncio.create_task → _update_persona_and_summary_background() [if flagged]
```

---

## Main Graph Nodes

**File:** `builder.py`  
**State:** `states.py` → `ChatbotState`

### Orchestrator Node (`temp=0.0`)

**File:** `nodes/orchestrator_node.py`

The Orchestrator is the first node in every request. It acts as a **query router and rewriter** — it reads the user query, the session summary, and the recent conversation history, then makes structured routing decisions using `RouteDecision` (via `function_calling`):

| Field | Type | Purpose |
|---|---|---|
| `needs_retrieval` | bool | True if the query requires fetching new data from the DB |
| `standalone_query` | str | Pronoun-resolved, context-independent version of the query |
| `needs_persona_update` | bool | True if the user reveals learning preferences or goals |
| `needs_summary_update` | bool | True if a new topic or milestone is introduced |

**Smart routing logic:**
- Returns `direct_answer` when the query is a follow-up on already-discussed content, a greeting, or a question about enrolled courses (already available in state).
- Returns `route_to_rag` when fresh database retrieval is needed.
- On prompt injection attempts, sets `needs_retrieval=False` and preserves the query for safe downstream handling by Luma.

---

### RAG Node

**File:** `nodes/rag_node.py`

A thin wrapper around the RAG subgraph. The content it retrieves originates from lectures parsed via **Azure AI Document Intelligence (OCR + structural analysis)** — meaning retrieved chunks carry intact section context, not arbitrary character fragments. It:
1. Passes the current state into the RAG subgraph (using `standalone_query` if available, otherwise `user_query`).
2. Injects `past_messages_tool_outputs` — deduplicated step outputs from the last 3 previous turns, enabling cross-turn context awareness.
3. Maps the subgraph output back into `ChatbotState`: `retrieved_context`, `run_step_outputs`, `rag_status`, `rag_clarification_question`, `rag_error_message`.

For the full RAG subgraph internals — DAG planning, parallel execution, Hybrid Search, RRF, Cohere reranking — see [`RAG_README.md`](agents/rag/RAG_README.md).

---

### Answering Node — Luma (`temp=0.7`)

**File:** `nodes/answering_node.py`

Luma is the final response generator. It's a **Socratic educational mentor** with a distinct persona enforced by its system prompt:

- Encourages understanding over fact-dumping; uses analogies, step-by-step breakdowns.
- Always concludes with a follow-up question to check student comprehension.
- Cites sources inline (lecture names, page references) from chunk metadata without exposing raw IDs.
- Responds in the student's preferred language.
- Refuses off-topic queries, prompt injection attempts, and out-of-scope content politely.

**Short-circuit logic:**
- If `rag_status == "failed"` → returns an error message without LLM invocation.
- If `rag_status == "clarification"` → returns the clarification question directly.

**Context fallback:** If `retrieved_context` is empty but `past_messages_tool_outputs` exist (from cross-turn memory), Luma extracts and formats them as a fallback retrieved context before generating the response.

**Message structure sent to LLM:**
```
SystemMessage(STATIC_SYSTEM_PROMPT)
[HumanMessage / AIMessage per message in messages_history]
SystemMessage(DYNAMIC_CONTEXT: persona + summary + courses + retrieved_context)
HumanMessage(user_query)
```

**LLM telemetry captured:** After each LLM call, the node extracts and returns `llm_usage` (prompt/completion/total tokens) and `llm_metadata` (model name, finish reason, system fingerprint) for the evaluation pipeline.

---

## Chains

**Directory:** `chains/`

| Chain | File | Temperature | Purpose |
|---|---|---|---|
| Summary | `chains/summary_chain.py` | 0.2 | Incremental merge of old summary + new interactions into a rolling session summary |
| Persona | `chains/persona_chain.py` | 0.1 | Classifies whether the persona document needs updating; outputs `PersonaUpdateDecision` with `should_update` + `updated_persona` |

Both chains run **in the background** via `asyncio.create_task` after the HTTP response is returned, avoiding any latency impact on the user.

---

## Session Lifecycle

| Event | API | What Happens |
|---|---|---|
| Session Start | `POST /session/start` | Load persona doc from MongoDB → write to Redis |
| Chat | `POST /assistant/chat` | Read `RedisSessionDTO` from Redis → run graph → update persona/summary → write back to Redis |
| Session End | `POST /session/end` | Archive session summary to Qdrant (semantic index) → upsert persona to MongoDB → clear Redis |

### RedisSessionDTO Fields

| Field | Description |
|---|---|
| `messages` | Full message history `[{role, content}]` (last 6 injected into graph) |
| `persona` | Student persona string (loaded from MongoDB, updated in-session) |
| `summary` | Rolling session summary |
| `student_courses` | Cached enrolled courses string (fetched from SQL on first request, cached for session) |
| `contexts` | `List[List[StepOutput]]` — per-turn tool outputs for cross-turn context (last 3 turns injected into RAG) |

---

## State Schema

**File:** `states.py`

```
ChatbotState
├── user_query                  str
├── student_id                  str
├── session_id                  str
├── student_courses             str
├── user_persona                str | None
├── session_summary             str | None
├── standalone_query            str | None      # rewritten query from Orchestrator
├── needs_persona_update        bool
├── needs_summary_update        bool
├── messages_history            List[Any]       # last 6 messages from Redis
├── past_messages_tool_outputs  List[StepOutput]   # last 3 turns deduplicated
├── retrieved_context           str | None
├── run_step_outputs            List[StepOutput]   # current turn → saved to Redis
├── rag_status                  str | None      # "route_to_rag" | "direct_answer" | "clarification" | "failed"
├── rag_clarification_question  str | None
├── rag_error_message           str | None
├── response                    str | None
├── llm_usage                   Dict | None     # token counts
└── llm_metadata                Dict | None     # model name, finish_reason, fingerprint
```

---

## Evaluation Pipeline (Fire-and-Forget)

After every chat response, `_push_evaluation()` is dispatched as a background `asyncio.create_task`. It constructs and persists an `EvaluationModel` document to MongoDB with four structured layers:

| Layer | Contents |
|---|---|
| `RequestLayer` | `user_query`, `session_id`, `student_id`, `context_data` (persona + summary) |
| `RetrievalLayer` | `final_context` (formatted retrieved context string), `raw_documents` (raw `StepOutput` list) |
| `GenerationLayer` | `final_answer`, `parameters` (model id + temperature), `metadata` (finish_reason, fingerprint) |
| `PerformanceLayer` | `latency_ms` (full graph wall-clock time), `token_usage` (prompt/completion/total) |

This enables offline RAG evaluation, quality monitoring, and response auditing without impacting request latency.

---

## LLM Map

Built in `ChatbotService.__init__` and passed to `build_chatbot_graph`. This is the single place to tune model configs per component:

| Key | Temperature | Used By |
|---|---|---|
| `orchestrator` | 0.0 | OrchestratorNode — deterministic routing decisions |
| `answering` | 0.7 | AnsweringNode (Luma) — creative, natural responses |
| `summary` | 0.2 | `summary_chain` — controlled rolling summary generation |
| `persona` | 0.1 | `persona_chain` — near-deterministic persona update decisions |

The RAG subgraph builds its own internal `rag_llm_map` from the same `lc_openai_client`.

---

## Utilities

**File:** `utils.py`

| Function | Purpose |
|---|---|
| `format_step_output(out, for_planning)` | Formats a single `StepOutput` for Planner/Reflection prompt injection |
| `format_nested_step_outputs(nested, for_planning)` | Formats `List[StepOutput]` organized by turn |
| `format_messages_history(messages)` | Converts `[{role, content}]` dicts to a readable string |
| `format_student_courses(courses)` | Formats SQL course list into a compact string for state injection |
| `format_chat_history_for_graph(messages, limit)` | Selects last N messages and formats them |
| `extract_clean_content_text(content)` | Extracts readable text from a `StepOutput.content` dict (chunks, summary, raw JSON) |
| `deduplicate_tool_outputs(outputs)` | Deduplicates a list of `StepOutput` by `(tool_name, tool_args)` key |

---

## LangGraph Studio

**File:** `studio.py`

Builds the full two-level graph for LangGraph Studio visualization. Uses a `MockRedisProvider` (no-op stub) so the graph compiles and renders without live infrastructure. The `llm_map` mirrors the production service exactly.

---

## Chatbot Exceptions

**File:** `chatbot_exceptions.py`

| Exception | HTTP Status | When Used |
|---|---|---|
| `ChatbotValidationError` | 422 | Empty/too-long query, missing student_id or session_id |
| `ChatbotProcessingError` | 500 | Graph invocation failure |
| `ChatbotExternalError` | 502 | External dependency failures (DB, LLM) |
