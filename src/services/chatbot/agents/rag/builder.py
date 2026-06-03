from typing import Any, Dict, List, Literal, Optional, Union, Callable
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI

from src.dtos import RAGContextDTO
from .states import RAGSubgraphState, ExecutionState, ReflectionDecision, RAGSubgraphOutput, PlannerOutput
from .nodes.planner import build_planner_chain
from .nodes.executer import executor_node
from .nodes.reflection import reflection_node, build_reflection_chain


def build_rag_subgraph(
    llm: ChatOpenAI,
    tool_registry: Dict[str, Callable]
):
    # 1. Initialize Chains
    planner_chain = build_planner_chain(llm)
    reflection_chain = build_reflection_chain(llm)

    # 2. Define Nodes
    async def run_planner_node(state: RAGSubgraphState) -> Dict[str, Any]:
        # Looping logic: clear previous execution items if needed, or keep for history?
        # The prompt says "Support reflection -> planner loop"
        output: PlannerOutput = await planner_chain.ainvoke({
            "user_query": state.user_query,
            "student_id": state.student_id
        })
        return {"planner_output": output}

    async def run_executor_node(state: RAGSubgraphState) -> Dict[str, Any]:
        result = await executor_node(state, tool_registry)
        return result

    async def run_reflection_node(state: RAGSubgraphState) -> Dict[str, Any]:
        result = await reflection_node(state, reflection_chain)
        return result

    # 3. Routing Logic
    def route_after_planner(state: RAGSubgraphState) -> Literal["executor", "end_clarification"]:
        if not state.planner_output:
            return "end_clarification"
        
        if state.planner_output.status == "clarification":
            return "end_clarification"
        return "executor"

    def route_after_reflection(state: RAGSubgraphState) -> Literal["planner", "end_success", "end_clarification"]:
        if not state.reflection_decision:
            return "end_success"
        
        decision = state.reflection_decision.decision
        if decision == "replan":
            return "planner"
        elif decision == "clarification":
            return "end_clarification"
        else:
            return "end_success"

    # 4. Final Output Node
    async def finalize_node(state: RAGSubgraphState) -> Dict[str, Any]:
        status = "success"
        clarification_question = None
        
        # Check clarification from reflection first
        if state.reflection_decision and state.reflection_decision.decision == "clarification":
            status = "clarification"
            clarification_question = state.reflection_decision.clarification_question
        # Then check clarification from planner
        elif state.planner_output and state.planner_output.status == "clarification":
            status = "clarification"
            clarification_question = state.planner_output.clarification_question
            
        return {
            "final_output": RAGSubgraphOutput(
                status=status,
                contexts=state.contexts,
                clarification_question=clarification_question
            )
        }

    # 5. Build Graph
    workflow = StateGraph(RAGSubgraphState)

    workflow.add_node("planner", run_planner_node)
    workflow.add_node("executor", run_executor_node)
    workflow.add_node("reflection", run_reflection_node)
    workflow.add_node("finalize", finalize_node)

    workflow.add_edge(START, "planner")
    
    workflow.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "executor": "executor",
            "end_clarification": "finalize"
        }
    )

    workflow.add_edge("executor", "reflection")

    workflow.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "planner": "planner",
            "end_success": "finalize",
            "end_clarification": "finalize"
        }
    )

    workflow.add_edge("finalize", END)

    return workflow.compile()



