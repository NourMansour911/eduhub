---
name: langgraph-agentic-workflow-builder
description: "Use when building or reviewing a multi-node LangGraph workflow, a cyclic DAG (Planner→Executor→Reflection loop), nested subgraphs, or graph compilation for LangGraph Studio."
---

# LangGraph Agentic Workflow Builder Skill

## Purpose

Defines the structural patterns for assembling LangGraph `StateGraph` workflows in this project — from simple linear DAGs to nested subgraphs with cyclic replan loops. Grounded in `builder.py` (chatbot and RAG levels).

## When To Use

- Creating a new `StateGraph` workflow.
- Adding cyclic routing (replan loops) to an existing graph.
- Nesting a compiled subgraph inside a parent graph.
- Compiling a graph variant for LangGraph Studio visualization.

---

## Pattern 1: The Graph Builder Class

Wrap `StateGraph` construction inside a builder class. Expose a single compiled graph via a standalone factory function.

```python
from typing import Dict
from langgraph.graph import StateGraph, END, START
from langgraph.graph.state import CompiledStateGraph
from langchain_openai import ChatOpenAI

from .states import MyGraphState
from .nodes.node_a import NodeA
from .nodes.node_b import NodeB


class MyGraph:
    def __init__(self, llm_map: Dict[str, ChatOpenAI], ...dependencies):
        # Instantiate all nodes once in __init__
        self.node_a = NodeA(llm=llm_map["node_a"])
        self.node_b = NodeB(llm=llm_map["node_b"], ...dependencies)
        self.graph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        workflow = StateGraph(MyGraphState)

        workflow.add_node("node_a", self.node_a)
        workflow.add_node("node_b", self.node_b)

        workflow.add_edge(START, "node_a")
        workflow.add_edge("node_a", "node_b")
        workflow.add_edge("node_b", END)

        return workflow.compile(name="MyGraph")


def build_my_graph(llm_map: Dict[str, ChatOpenAI], ...) -> CompiledStateGraph:
    return MyGraph(llm_map=llm_map, ...).graph
```

**Rules:**
- All nodes are instantiated in `__init__` — never in `_build_graph`.
- `_build_graph` only wires nodes; no business logic.
- Always pass `name=` to `.compile()` for LangGraph Studio identification.
- Expose a module-level factory function (`build_my_graph`) as the public API.

---

## Pattern 2: Conditional Routing (Linear with Branching)

```python
def _route_after_orchestrator(self, state: MyGraphState) -> str:
    # Read from state — never compute here
    if state.rag_status == "route_to_rag":
        return "rag_node"
    return "answering"

# Wire the conditional edge in _build_graph:
workflow.add_conditional_edges(
    "orchestrator",
    self._route_after_orchestrator,
    {
        "rag_node":  "rag_node",
        "answering": "answering",
    }
)
```

**Rules:**
- Router functions read state flags set by upstream nodes — they never call LLMs or compute.
- The router function returns a **string key** matching the dict passed to `add_conditional_edges`.
- Route function lives as a method of the builder class (`self._route_*`).

---

## Pattern 3: Cyclic DAG (Planner → Executor → Reflection Loop)

```python
def _build_graph(self) -> CompiledStateGraph:
    workflow = StateGraph(RAGSubgraphState)

    workflow.add_node("planner",             self.planner_node)
    workflow.add_node("executor",            self.executor_node)
    workflow.add_node("reflection",          self.reflection_node)
    workflow.add_node("finalize_and_aggregate", self._finalize_node)

    workflow.add_edge(START, "planner")

    workflow.add_conditional_edges(
        "planner",
        self._route_after_planner,
        {"executor": "executor", "route_to_clarification": "finalize_and_aggregate"},
    )

    workflow.add_edge("executor", "reflection")

    workflow.add_conditional_edges(
        "reflection",
        self._route_after_reflection,
        {
            "planner":                "planner",         # replan cycle
            "route_to_success":       "finalize_and_aggregate",
            "route_to_clarification": "finalize_and_aggregate",
        },
    )

    workflow.add_edge("finalize_and_aggregate", END)
    return workflow.compile(name="RAGSubgraph")

def _route_after_planner(self, state) -> Literal["executor", "route_to_clarification"]:
    if not state.planner_output or state.planner_output.status == "clarification":
        return "route_to_clarification"
    return "executor"

def _route_after_reflection(self, state) -> Literal["planner", "route_to_success", "route_to_clarification"]:
    if not state.reflection_decision:
        return "route_to_success"
    decision = state.reflection_decision.decision
    if decision == "replan":
        return "planner" if state.plan_attempts_count < 2 else "route_to_success"
    if decision == "clarification":
        return "route_to_clarification"
    return "route_to_success"
```

**Cyclic DAG Rules:**
- The `replan` cycle goes back to `"planner"` only when `plan_attempts_count < MAX_ATTEMPTS`.
- The Planner node increments `plan_attempts_count` in its state delta return.
- The `finalize_and_aggregate` node is a single convergence point — all terminal routes lead here.
- `finalize_and_aggregate` is always an `async def` on the builder class, not a separate node class, because it contains graph-level aggregation logic.

---

## Pattern 4: Nested Subgraph (Parent → Subgraph)

```python
# In the parent builder, accept the pre-compiled subgraph:
class ChatbotGraph:
    def __init__(self, llm_map, rag_subgraph: CompiledStateGraph, ...):
        self.rag_node = RAGNode(rag_subgraph)   # node wraps subgraph

# RAGNode wraps and invokes the subgraph:
class RAGNode:
    def __init__(self, rag_subgraph: CompiledStateGraph):
        self.rag_subgraph = rag_subgraph

    async def __call__(self, state: ChatbotState) -> Dict[str, Any]:
        result = await self.rag_subgraph.ainvoke({
            "user_query":       state.standalone_query or state.user_query,
            "student_id":       state.student_id,
            "session_id":       state.session_id,
            "student_courses":  state.student_courses,
            "messages_history": state.messages_history,
        })
        subgraph_output = result.get("retriving_results")
        # Map subgraph output back into parent state
        return {
            "retrieved_context":        subgraph_output.retrieved_context,
            "run_step_outputs":         subgraph_output.run_step_outputs,
            "rag_status":               subgraph_output.status,
            "rag_clarification_question": subgraph_output.clarification_question,
            "rag_error_message":        subgraph_output.error_message,
        }
```

**Rules:**
- Subgraphs are built and compiled independently, then passed in as compiled objects.
- The wrapper node maps **parent state → subgraph input** and **subgraph output → parent state delta**.
- Never import subgraph state into parent state — use explicit field mapping.

---

## Pattern 5: LangGraph Studio Compilation (`studio.py`)

Every graph module MUST have a `studio.py` that builds the full graph with mock providers for visualization:

```python
# studio.py — no live infrastructure needed
from integrations.llm import LCOpenAI
from integrations.redis_provider import RedisProvider  # or MockRedisProvider

class MockRedisProvider:
    """No-op stub for Studio compilation — no live Redis needed."""
    async def get_collection(self, *args, **kwargs): return None
    async def save_collection(self, *args, **kwargs): return None

lc_openai_client = LCOpenAI(api_key="studio_key", api_url="http://localhost")
redis_provider    = MockRedisProvider()

# Build the full graph — mirrors production exactly
graph = build_my_graph(
    lc_openai_client=lc_openai_client,
    redis_provider=redis_provider,
    ...
)
```

**Rules:**
- `studio.py` uses the same `llm_map` temperatures as production.
- Mock providers are minimal no-op stubs — never shared with production code.
- The `graph` variable must be named `graph` (LangGraph Studio convention).

---

## LLM Map Convention

Every graph that uses multiple LLMs MUST receive a pre-built `llm_map` dict. Temperature decisions are made by the **service layer**, not inside the graph builder:

```python
llm_map = {
    "orchestrator": lc_openai_client.get_langchain_llm(model=..., temperature=0.0),
    "answering":    lc_openai_client.get_langchain_llm(model=..., temperature=0.7),
    "summary":      lc_openai_client.get_langchain_llm(model=..., temperature=0.2),
    "persona":      lc_openai_client.get_langchain_llm(model=..., temperature=0.1),
}
```

The builder class pulls from this map: `self.node_a = NodeA(llm=llm_map["node_a"])`.

---

## File Structure

```
src/services/<feature>/
├── builder.py          # Parent graph builder + factory function
├── states.py           # Parent graph state schema
├── studio.py           # LangGraph Studio visualization entry point
├── nodes/
│   ├── node_a.py
│   └── node_b.py
└── agents/
    └── <subgraph>/
        ├── builder.py  # Subgraph builder + factory function
        ├── states.py   # Subgraph state schemas
        └── nodes/
            ├── planner.py
            ├── executer.py
            └── reflection.py
```

## Review Checklist

- Is the graph assembled in a builder class, not a bare function?
- Are all nodes instantiated in `__init__`, not in `_build_graph`?
- Are routing functions reading state flags (not computing)?
- Does the cyclic DAG have a `plan_attempts_count` guard to prevent infinite loops?
- Is `finalize_and_aggregate` the single convergence point for all terminal routes?
- Does `studio.py` exist and use mock providers?
- Does the LLM map come from the service layer, not the builder?
