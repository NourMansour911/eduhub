from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from core import Settings
from integrations.llm import LCOpenAI

from .nodes.planner import build_planner_chain


class RAGSubgraphState(TypedDict, total=False):
    user_query: str
    plan: List[Dict[str, Any]]


def build_rag_subgraph(
    lc_openai_client: LCOpenAI,
    settings: Settings,

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

        return {
            "plan": await planner_chain.ainvoke({"user_query": user_query}),
        }

    graph = StateGraph(RAGSubgraphState)
    graph.add_node("planner", RunnableLambda(run_planner))
    graph.add_edge(START, "planner")
    graph.add_edge("planner", END)

    return graph.compile()


