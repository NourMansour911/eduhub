from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, TypedDict, Union

from langchain_core.runnables import Runnable, RunnableLambda
from langgraph.graph import END, START, StateGraph

from core import Settings
from integrations.llm import LCOpenAI

from .nodes.executer import execute_plan, ExecuterError
from .nodes.planner import Plan, build_planner_chain


class RAGSubgraphState(TypedDict, total=False):
    user_query: str
    student_id: str
    plan: Any
    reflection: str


def build_rag_subgraph(
    lc_openai_client: LCOpenAI,
    settings: Settings,
    tool_source: Optional[Union[Mapping[str, Callable[..., Any]], Iterable[Any]]] = None,
):
    planner_llm = lc_openai_client.get_langchain_llm(
        model=settings.GENERATION_MODEL_ID,
        temperature=0.0,
    )

    planner_chain: Runnable = build_planner_chain(planner_llm)

    async def run_planner(state: RAGSubgraphState) -> Dict[str, Any]:
        user_query = (state.get("user_query") or "").strip()
        if not user_query:
            raise ValueError("user_query is required")

        student_id = (state.get("student_id") or "").strip()
        if not student_id:
            raise ValueError("student_id is required")

        return {
            "plan": await planner_chain.ainvoke({"user_query": user_query, "student_id": student_id}),
        }

    async def handle_planner_output(state: RAGSubgraphState) -> Dict[str, Any]:
        planner_output = state.get("plan")
        if planner_output is None:
            raise ValueError("Planner output is missing")

        plan = getattr(planner_output, "result", None)
        if plan is None:
            raise ValueError("Planner result is missing")

        status = getattr(plan, "status", None)
        if status == 0:
            question = getattr(plan, "question", None)
            if question is None and isinstance(plan, dict):
                question = plan.get("question", "Unknown reason")
            if question is None:
                question = "Unknown reason"
            return {"reflection": f"Planner could not build an executable plan: {question}"}

        
        plan = Plan.model_validate(plan)
        if tool_source is not None:
            try:
                return await execute_plan(plan, tool_source, runtime_context={"student_id": state["student_id"]})
            except ExecuterError as exc:
                return {"reflection": str(exc)}

        return {"plan": plan}

    graph = StateGraph(RAGSubgraphState)
    graph.add_node("planner", RunnableLambda(run_planner))
    graph.add_node("planner_output", RunnableLambda(handle_planner_output))
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "planner_output")
    graph.add_edge("planner_output", END)

    return graph.compile()


