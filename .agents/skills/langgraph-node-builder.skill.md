---
name: langgraph-node-builder
description: "Use when creating, refactoring, or reviewing any LangGraph node in this project. Defines the canonical callable-class node pattern including prompt separation, structured LLM output, telemetry extraction, state delta returns, and short-circuit guards."
---

# LangGraph Node Builder Skill

## Purpose

Every LangGraph node in this project follows a single canonical pattern: an **async callable class** that encapsulates its own prompt template, chain construction, and telemetry extraction. This skill defines that pattern exactly — grounded in `nodes/orchestrator_node.py`, `nodes/answering_node.py`, `agents/rag/nodes/planner.py`, and `agents/rag/nodes/reflection.py`.

## When To Use

- Creating a new LangGraph node (any graph level).
- Refactoring an existing node function into the class pattern.
- Reviewing a node for structural compliance.
- Adding telemetry, short-circuit logic, or structured output to an existing node.

---

## Core Pattern: The Async Callable Node Class

Every node MUST follow this exact structure:

```python
from typing import Any, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ..states import GraphState           # import from centralized states.py
from helpers.logger import get_chatbot_logger
from ..utils import extract_llm_usage, extract_llm_metadata, build_llm_node_payload

logger = get_chatbot_logger(__name__)


class MyOutputSchema(BaseModel):
    field_one: str = Field(..., description="Clear description for the LLM.")
    field_two: bool = Field(..., description="Clear description for the LLM.")


class MyNode:
    # --- 1. STATIC system prompt (compiled once, never changes per request) ---
    STATIC_SYSTEM_PROMPT = """
You are ...

Rules:
1. ...
2. ...
"""

    # --- 2. DYNAMIC context template (hydrated per request at call time) ---
    DYNAMIC_CONTEXT_TEMPLATE = """
{variable_one}

{variable_two}

Current Query: {user_query}
"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        # Build the full chain once in __init__. Never rebuild in __call__.
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.STATIC_SYSTEM_PROMPT),
            ("human", self.DYNAMIC_CONTEXT_TEMPLATE),
        ])
        # Use include_raw=True to access token usage metadata alongside parsed output.
        self.chain = self.prompt | llm.with_structured_output(
            MyOutputSchema, method="function_calling", include_raw=True
        )

    async def __call__(self, state: GraphState) -> Dict[str, Any]:
        # --- 3. SHORT-CIRCUIT: check graph state flags before calling the LLM ---
        if state.some_error_flag:
            return {"response": "Error short-circuit message"}

        # --- 4. PREPARE inputs (read from state, format as needed) ---
        variable_one = state.field_one or "Default value"
        variable_two = state.field_two or "Default value"

        logger.info("MyNode invoked. Query: %s", state.user_query)

        # --- 5. INVOKE chain ---
        raw_result = await self.chain.ainvoke({
            "variable_one": variable_one,
            "variable_two": variable_two,
            "user_query": state.user_query,
        })

        # --- 6. EXTRACT structured output and telemetry ---
        output: MyOutputSchema = raw_result["parsed"]
        usage = extract_llm_usage(raw_result.get("raw"))
        metadata = extract_llm_metadata(raw_result.get("raw"), self.llm)

        logger.info("MyNode decision: field_one=%s, field_two=%s", output.field_one, output.field_two)

        # --- 7. RETURN delta state (only the keys this node is responsible for) ---
        return {
            "field_one":  output.field_one,
            "field_two":  output.field_two,
            "llm_usage_breakdown": {"my_node": build_llm_node_payload(usage, metadata)},
        }
```

---

## Rule 1: Prompt Separation — Static vs. Dynamic

| Component | Location | Content | Compiled |
|---|---|---|---|
| `STATIC_SYSTEM_PROMPT` | Class-level constant | Role definition, fixed rules, behavioral constraints | Once at class definition |
| `DYNAMIC_CONTEXT_TEMPLATE` | Class-level constant | Placeholders for per-request data (session summary, history, user query) | Hydrated in `__call__` via `.ainvoke({...})` |

**Rules:**
- The static prompt MUST NOT contain any per-request data (no f-strings, no `.format()`).
- The dynamic template MUST use `{placeholder}` syntax matching the `.ainvoke({...})` dict keys exactly.
- Both are class-level string constants, never rebuilt per call.

```python
# CORRECT — static stays static
STATIC_SYSTEM_PROMPT = """
You are a Router. Analyze the user query.
Rules:
1. Set needs_retrieval=True for academic content questions.
2. Set needs_retrieval=False for greetings and chit-chat.
"""

DYNAMIC_CONTEXT_TEMPLATE = """
Session Summary: {session_summary}
Recent History: {messages_history}
User Query: {user_query}
"""
```

---

## Rule 2: Structured Output Binding

Use `.with_structured_output()` exclusively for typed node outputs:

```python
# ALWAYS include_raw=True — needed for token usage extraction
self.chain = self.prompt | llm.with_structured_output(
    MyOutputSchema, method="function_calling", include_raw=True
)

# Extract from raw result dict
output: MyOutputSchema = raw_result["parsed"]
usage = extract_llm_usage(raw_result.get("raw"))
metadata = extract_llm_metadata(raw_result.get("raw"), self.llm)
```

For nodes that produce free-text output (not structured), call `.ainvoke()` directly on the LLM and extract usage from the response object:

```python
# Free-text node (e.g., AnsweringNode)
response = await self.llm.ainvoke(messages)
usage = extract_llm_usage(response)      # pass the AIMessage directly
metadata = extract_llm_metadata(response, self.llm)
```

---

## Rule 3: Delta State Returns

Nodes MUST return only the fields they mutate. Never return the entire state.

```python
# CORRECT — delta return
return {
    "rag_status":        rag_status,
    "standalone_query":  decision.standalone_query,
    "needs_persona_update": decision.needs_persona_update,
    "llm_usage_breakdown": {"orchestrator": build_llm_node_payload(usage, metadata)},
}

# WRONG — returning full state
return state.model_copy(update={...}).model_dump()
```

**LLM Usage Pattern in State:**
When a graph has multiple LLM nodes, track usage as a keyed dict, **not a flat sum**:

```python
# Accumulate — read existing dict, add this node's key, return updated dict
existing = dict(state.llm_usage_breakdown)
existing["my_node"] = build_llm_node_payload(usage, metadata)
# If this is the FINAL node, compute and store the total:
existing["total"] = build_llm_node_payload(sum_llm_usage_tree(existing), {})
return {"llm_usage_breakdown": existing}
```

The key naming convention:
- Single attempt nodes: `"orchestrator"`, `"answering"`, `"rag_node"`
- Multi-attempt nodes (e.g., Planner/Reflection in cyclic DAG): `f"planner_{state.plan_attempts_count}"`, `f"reflection_{state.plan_attempts_count}"`

---

## Rule 4: Short-Circuit Guards

Nodes that run conditionally MUST check graph state flags **before invoking the LLM**:

```python
async def __call__(self, state: GraphState) -> Dict[str, Any]:
    # Short-circuit first — no LLM call if in failed/clarification state
    if state.rag_status == "failed":
        return {"response": f"Error: {state.rag_error_message}"}
    if state.rag_status == "clarification":
        return {"response": state.rag_clarification_question}

    # Normal execution path follows...
```

For Executor-type nodes (no LLM), guard on planner output before executing tools:
```python
if not planner_output or planner_output.status != "plan" or not planner_output.steps:
    return {}   # Empty dict = no state update needed
```

---

## Rule 5: Multi-Dependency Constructor (Provider-Injected Nodes)

Some nodes need more than an LLM (e.g., Redis, tool registries). Accept them in `__init__`:

```python
class AnsweringNode:
    def __init__(self, llm_map: Dict[str, ChatOpenAI], redis_provider: RedisProvider):
        self.llm: ChatOpenAI = llm_map["answering"]   # pull specific LLM from map
        self.redis_provider = redis_provider
        # No chain built here — this node manually constructs messages per call
```

For nodes using a **tool registry** (Executor pattern):

```python
class ExecutorNode:
    def __init__(self, tool_registry: Dict[str, Callable]):
        self.tool_registry = tool_registry
        # No LLM — this node orchestrates async tool calls
```

---

## Rule 6: Logging Standards

Every node MUST log at entry (info) and at decision point (info):

```python
# Entry log — include the key routing input
logger.info("MyNode invoked. Query: %s", state.user_query)

# Decision log — include all key output fields
logger.info(
    "MyNode decision: field_one=%s, field_two=%s, field_three=%s",
    output.field_one, output.field_two, output.field_three,
)
```

For verbose intermediate diagnostics, use `logger.debug`.

For structured block logging (multi-line diagnostics), use the block pattern:
```python
logger.info(
    "\n" + "="*80 + "\n"
    "[MY NODE] STARTING EVALUATION\n"
    f"Session ID: {state.session_id}\n"
    f"Attempt: {state.plan_attempts_count}\n"
    f"User Query: {state.user_query}\n"
    + "="*80
)
```

---

## Rule 7: Message Construction for Free-Text Nodes

Nodes that manually construct message lists for the LLM (no `ChatPromptTemplate`) follow this exact order:

```python
messages = [
    SystemMessage(content=self.STATIC_SYSTEM_PROMPT),             # 1. Static role
]
for msg in state.messages_history:                                 # 2. Conversation history
    if msg.get("role") == "Human":
        messages.append(HumanMessage(content=msg["content"]))
    elif msg.get("role") == "AI":
        messages.append(AIMessage(content=msg["content"]))

messages.append(SystemMessage(content=dynamic_context_content))   # 3. Dynamic context
messages.append(HumanMessage(content=state.user_query))           # 4. Current query
```

---

## File Placement

```
src/services/<feature>/nodes/<node_name>.py         # top-level graph nodes
src/services/<feature>/agents/<subgraph>/nodes/<node_name>.py   # subgraph nodes
```

Each node file is standalone — one class per file, no shared state between files.

## Review Checklist

- Is the node an async callable class (`async def __call__`)?
- Are `STATIC_SYSTEM_PROMPT` and `DYNAMIC_CONTEXT_TEMPLATE` class-level string constants?
- Is the chain (prompt + LLM) built once in `__init__`, never rebuilt in `__call__`?
- Is `include_raw=True` used for structured output binding?
- Are LLM usage and metadata extracted via `extract_llm_usage` / `extract_llm_metadata`?
- Does the node return only a **delta dict** of mutated state keys?
- Are short-circuit guards checked **before** any LLM invocation?
- Is the LLM usage keyed by node name, not a flat total?
- Are entry + decision logs present?
