---
name: workflow-state-data-exchange
description: "Use when designing, refactoring, or reviewing LangGraph state schemas, message history handling, tool output management, or data exchange between graph nodes and subgraphs."
---

# Workflow State & Data Exchange Skill

## Purpose

Defines all conventions for state schema design, cross-node data exchange, message clipping, tool output deduplication, and context formatting in LangGraph workflows. Grounded in `states.py` (chatbot + RAG), `utils.py`, and the service layer's session data preparation.

## When To Use

- Creating a new `StateGraph` state schema.
- Adding a new field to an existing state.
- Writing a node that reads from or writes to graph state.
- Handling message history or tool output formatting between nodes.

---

## Rule 1: Centralized State Schema in `states.py`

Every graph level has exactly ONE `states.py`. All state classes and shared output schemas for that level live there. No state definitions scattered across node files.

```python
# src/services/<feature>/states.py  ← parent graph states
# src/services/<feature>/agents/<subgraph>/states.py  ← subgraph states
```

**Why:** Prevents circular imports between node files that need to share output schemas.

### State Design Rules

```python
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class MyGraphState(BaseModel):
    # --- Identity fields (always str, always required) ---
    user_query:   str
    student_id:   str
    session_id:   str

    # --- Input context (loaded before graph invocation) ---
    student_courses:   str = ""
    messages_history:  List[Any] = Field(default_factory=list)

    # --- Routing flags (written by one node, read by router + downstream) ---
    rag_status:   Optional[str] = None   # "route_to_rag" | "direct_answer" | "clarification" | "failed"

    # --- Accumulated results (nodes append/update, never overwrite peers' keys) ---
    retrieved_context:   Optional[str]  = None
    run_step_outputs:    List[Any]      = Field(default_factory=list)

    # --- Final output ---
    response:     Optional[str]  = None

    # --- Telemetry (hierarchical dict, keyed by node name) ---
    llm_usage_breakdown: Dict[str, Any] = Field(default_factory=dict)
```

**Rules:**
- Use `Optional[T] = None` for fields written by downstream nodes.
- Use `Field(default_factory=list)` for list fields — never `= []`.
- Routing flag fields (`rag_status`, `reflection_decision`, etc.) are always `Optional`.
- Telemetry fields are always `Dict[str, Any]` with `default_factory=dict`.
- State models are **Pydantic BaseModel** — never TypedDict or plain dataclass.

---

## Rule 2: Subgraph Output Schema

When a subgraph produces a result that is consumed by the parent, package the result in a typed output model and store it as a single state field:

```python
# In subgraph states.py
class RAGSubgraphOutput(BaseModel):
    status:               Literal["success", "clarification", "failed"]
    retrieved_context:    Optional[str] = None
    run_step_outputs:     List[StepOutput] = Field(default_factory=list)
    clarification_question: Optional[str] = None
    error_message:        Optional[str] = None
    rag_llm_usage:        Dict[str, Any]  = Field(default_factory=dict)

# In subgraph state
class RAGSubgraphState(BaseModel):
    ...
    retriving_results: Optional[RAGSubgraphOutput] = None  # written by finalize node
```

The parent graph's wrapper node maps `retriving_results` fields back into parent state explicitly. No parent state field ever references subgraph state classes directly.

---

## Rule 3: Message History Clipping

Message content MUST be clipped before passing into any LLM node. Raw full-length messages are stored only in Redis/DB — never passed raw to the graph.

```python
# src/services/chatbot/utils.py
def clip_message_content(content: str, max_length: int = 500) -> str:
    if not content:
        return ""
    if len(content) <= max_length:
        return content
    return content[:max_length] + " [clipped for brevity]"


def format_chat_history_for_graph(messages: List[Dict], limit: int = 6) -> List[Dict]:
    last_messages = []
    for msg in messages[-limit:]:           # take last N turns
        role    = "Human" if msg.get("role") == "user" else "AI"
        content = clip_message_content(msg.get("content", ""))
        last_messages.append({"role": role, "content": content})
    return last_messages
```

**Conventions:**
- Default clip length: **500 characters**.
- Default history limit: **last 6 messages** (3 turns).
- Clipped messages are marked with `[clipped for brevity]` so LLMs know context is truncated.
- Call `format_chat_history_for_graph` in the **service layer** before `graph.ainvoke()`, not inside nodes.

---

## Rule 4: Tool Output Deduplication

Before injecting cross-turn tool outputs from Redis into the RAG subgraph, deduplicate by `(tool_name, tool_args)`:

```python
def deduplicate_tool_outputs(outputs: List[Any]) -> List[Any]:
    seen_keys = set()
    deduped   = []
    for out in reversed(outputs):           # last occurrence wins
        t_name    = getattr(out, "tool_name", "") or out.get("tool_name", "")
        t_args    = getattr(out, "tool_args", {}) or out.get("tool_args", {})
        t_args_str = json.dumps(t_args, sort_keys=True)
        key = (t_name, t_args_str)
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(out)
    deduped.reverse()
    return deduped
```

Apply deduplication:
1. When merging `past_attempts` + `current_attempt` inside the Planner node.
2. When injecting Redis `contexts` (cross-turn history) into the subgraph state.
3. In the `finalize_and_aggregate` node before building `retrieved_context`.

---

## Rule 5: `StepOutput` — The Tool Result Container

Every tool call result is wrapped in a `StepOutput`. This is the universal data unit for tool results across planning, execution, reflection, and storage:

```python
class FailureInfo(BaseModel):
    message:               str
    clarification_message: Optional[str] = None   # question to show the user
    explanation:           Optional[str] = None    # diagnostic detail for the LLM

class StepOutput(BaseModel):
    step_id:     str             = Field(default="")
    tool_name:   str             = Field(default="")
    tool_args:   Dict[str, Any]  = Field(default_factory=dict)
    source:      str             = Field(...)           # required: human-readable source label
    content:     Dict[str, Any]  = Field(default_factory=dict)   # populated on success
    failure_info: Optional[FailureInfo] = None          # populated on failure
```

**Rules:**
- `failure_info is None` → success.
- `failure_info is not None` → failure. Never use boolean flags or status codes.
- Tools MUST return `StepOutput` — they MUST NOT raise exceptions for expected failures.
- Only catastrophic infrastructure failures (e.g., DB completely unreachable) justify raising.

---

## Rule 6: Format Utilities

All string formatting for LLM injection lives in `utils.py`. Nodes MUST import and use these — never write inline formatters inside node files:

| Utility | Purpose | Call site |
|---|---|---|
| `format_step_output(out, for_planning)` | Formats a single `StepOutput` as text for LLM prompts | Planner, Reflection nodes |
| `format_nested_step_outputs(nested)` | Formats a list of `StepOutput` | Planner (past attempts) |
| `format_messages_history(messages)` | Converts `[{role, content}]` list to readable string | Orchestrator node |
| `format_chat_history_for_graph(messages, limit)` | Clips + selects last N messages | Service layer before `ainvoke` |
| `clip_message_content(content, max_length)` | Clips a single message string | Service layer, background tasks |
| `extract_clean_content_text(content)` | Extracts readable text from `StepOutput.content` | `finalize_and_aggregate` node |
| `deduplicate_tool_outputs(outputs)` | Deduplicates by `(tool_name, tool_args)` | Planner node, finalize node |

---

## Rule 7: Cross-Turn Context (Redis `contexts` field)

The service layer maintains a `contexts: List[List[StepOutput]]` in Redis — one inner list per turn:

```python
# After each chat turn, append this turn's tool outputs:
if run_step_outputs:
    collection.contexts.append(run_step_outputs)

# Before next turn's graph invocation, inject last 3 turns deduplicated:
flattened     = [out for turn in collection.contexts[-3:] for out in turn]
cross_turn    = deduplicate_tool_outputs(flattened)
# Pass cross_turn into subgraph state as past_attempts_tool_outputs
```

---

## Review Checklist

- Is the state schema in a centralized `states.py`, not spread across node files?
- Are all list fields using `Field(default_factory=list)`?
- Are all Optional node-written fields initialized to `None`?
- Is message history clipped (`clip_message_content`) before `graph.ainvoke()`?
- Is tool output deduplication applied before injecting into graph state?
- Are all tool results wrapped in `StepOutput` with `failure_info` (not exceptions)?
- Are string formatters imported from `utils.py`, not rewritten inside nodes?
