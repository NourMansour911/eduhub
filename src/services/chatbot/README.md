# Chatbot Service

Entry point: chatbot_service.py -> ChatbotService.chat()

The service owns session state (via Redis), builds the LLM map, and coordinates the LangGraph chatbot graph. The graph itself is a two-level structure: a main graph with three nodes and a RAG subgraph that handles all retrieval.

---

## High-Level Flow

```
HTTP POST /assistant/chat/{user_id}/{session_id}
  │
  ▼
ChatbotService.chat()
  ├── Load Redis session (messages, persona, summary, contexts, courses)
  ├── Invoke chatbot graph
  │     │
  │     ▼
  │   [Orchestrator] ── retrieve ──► [RAG Node] ──► [Answering (Luma)]
  │         └────────── direct ──────────────────► [Answering (Luma)]
  │
  ├── Save updated session to Redis
  └── asyncio.create_task → push LLM judge doc to MongoDB (fire-and-forget)
```

---

## Main Graph Nodes

### Orchestrator (temp=0.0)
Takes user_query only. Decides between retrieve (needs external data) and direct (can answer from history/summary alone). Returns rag_status.

### RAG Node
Wraps the RAG subgraph. Serializes previous_steps_outputs (last 3 turns from Redis) and passes them in. Returns retrieved_context, run_step_outputs, and RAG status fields. See RAG_README for full details.

### Answering Node — Luma (temp=0.7)
Tool-calling agent. Receives the full state (context, persona, summary, history) and runs a tool-calling loop with two tools:
- update_session_summary — incremental summary merge via summary_chain
- update_student_persona — persona analysis via persona_chain

Both tools are async coroutines. When called, they write directly to Redis via callbacks and update local state. The node returns response, user_persona, and session_summary.

If rag_status == "failed" or "clarification", Luma short-circuits and returns the appropriate message directly.
Out-of-scope queries (unrelated to courses/academics) are handled by Luma's system prompt — it responds with a polite refusal without calling any tools.

---

## Chains

| Chain | File | Temperature | Purpose |
|---|---|---|---|
| Summary | chains/summary_chain.py | 0.2 | Incremental merge of old summary + new interaction |
| Persona | chains/persona_chain.py | 0.1 | Classify whether persona needs update; output PersonaUpdateDecision |
| Orchestrator route | inline in OrchestratorNode | 0.0 | RouteDecision pydantic output |

---

## LLM Map

Built in ChatbotService.__init__ and passed to build_chatbot_graph. The map is the single place to tune model configs per component:

| Key | Temperature | Used by |
|---|---|---|
| orchestrator | 0.0 | OrchestratorNode |
| answering | 0.7 | AnsweringNode (Luma agent) |
| summary | 0.2 | build_summary_chain inside AnsweringNode |
| persona | 0.1 | build_persona_chain inside AnsweringNode |

The RAG subgraph builds its own internal rag_llm_map from the passed lc_openai_client.

---

## Session Lifecycle

| Event | What happens |
|---|---|
| POST /session/start | Load persona from MongoDB -> write to Redis |
| POST /assistant/chat | Read from Redis -> run graph -> write back to Redis |
| Tool callbacks (in-turn) | Persona/summary written to Redis immediately during answering |
| POST /session/end | Archive summary to Qdrant VDB -> upsert persona to MongoDB -> clear Redis |

---

## State (ChatbotState)

| Field | Type | Source |
|---|---|---|
| user_query | str | request |
| student_id, session_id | str | request |
| student_courses | str | Redis (cached) / SQL |
| messages_history | List[dict] | last 4 messages from Redis |
| user_persona | str | None | Redis |
| session_summary | str | None | Redis |
| previous_steps_outputs | List[List[StepOutput]] | last 3 turns from Redis contexts |
| retrieved_context | str | None | RAG Node output |
| run_step_outputs | List[StepOutput] | RAG Node output -> saved to Redis contexts |
| rag_status | str | None | Orchestrator / RAG Node |
| response | str | None | Answering Node |

---

## Tools (Agent Tools)

Both tools are StructuredTool async coroutines, created fresh per request with closures that capture the current state:

- update_session_summary(new_interactions: str) — calls summary_chain.ainvoke then the Redis callback
- update_student_persona() — calls persona_chain.ainvoke, checks should_update, then the Redis callback

---

## Utilities (utils.py)

- format_step_output(out) — formats a single StepOutput for prompt injection
- format_nested_step_outputs(nested) — formats List[List[StepOutput]] by turn
- format_messages_history(messages) — formats [{role, content}] dicts into readable string

---

## Studio (studio.py)

Builds the full graph for LangGraph Studio visualization. Uses MockRedisProvider (no-op stub) so the graph compiles without real infrastructure. The llm_map mirrors the service exactly.
