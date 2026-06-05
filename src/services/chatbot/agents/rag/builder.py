from typing import Any, Dict, List, Literal, Optional, Union, Callable
from langgraph.graph import StateGraph, END, START
from integrations.llm import LCOpenAI

from .states import RAGSubgraphState, RAGSubgraphOutput
from .nodes.planner import PlannerNode
from .nodes.executer import ExecutorNode
from .nodes.reflection import ReflectionNode
from core import Settings

from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools


class RAGSubgraph:
    def __init__(
        self,
        lc_openai_client: LCOpenAI,
        settings: Settings,
        vdb_tools: VDBTools,
        mongodb_tools: MongoDBTools,
        sql_tools: SQLTools,
    ):
        actual_tools = {
            "ask_in_specific_lecture_by_lecture_id": vdb_tools.ask_in_specific_lecture_by_lecture_id,
            "ask_in_the_whole_course_by_course_id": vdb_tools.ask_in_the_whole_course_by_course_id,
            "search_in_sessions_history": vdb_tools.search_in_sessions_history,
            "ask_in_legal_regulations": vdb_tools.ask_in_legal_regulations,
            
            "get_lecture_whole_content_by_lecture_id": mongodb_tools.get_lecture_whole_content_by_lecture_id,
            "get_lecture_summary_by_lecture_id": mongodb_tools.get_lecture_summary_by_lecture_id,
            
            "get_lecture_id_by_lecture_name": sql_tools.get_lecture_id_by_lecture_name,
            "get_course_details_by_course_id": sql_tools.get_course_details_by_course_id,
            "get_all_course_lectures_by_course_id": sql_tools.get_all_course_lectures_by_course_id,
        }
        
        planner_llm = lc_openai_client.get_langchain_llm(model=settings.GENERATION_MODEL_ID, temperature=0.1)
        reflection_llm = lc_openai_client.get_langchain_llm(model=settings.GENERATION_MODEL_ID, temperature=0.1)

        self.planner_node = PlannerNode(planner_llm)
        self.executor_node = ExecutorNode(tool_registry=actual_tools)
        self.reflection_node = ReflectionNode(reflection_llm)

        
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(RAGSubgraphState)

        workflow.add_node("planner", self.planner_node)
        workflow.add_node("executor", self.executor_node)
        workflow.add_node("reflection", self.reflection_node)
        workflow.add_node("finalize", self._finalize_node)

        workflow.add_edge(START, "planner")
        
        workflow.add_conditional_edges(
            "planner",
            self._route_after_planner,
            {
                "executor": "executor",
                "end_clarification": "finalize"
            }
        )

        workflow.add_edge("executor", "reflection")

        workflow.add_conditional_edges(
            "reflection",
            self._route_after_reflection,
            {
                "planner": "planner",
                "end_success": "finalize",
                "end_clarification": "finalize"
            }
        )

        workflow.add_edge("finalize", END)

        return workflow.compile()

    def _route_after_planner(self, state: RAGSubgraphState) -> Literal["executor", "end_clarification"]:
        if not state.planner_output or state.planner_output.status == "clarification":
            return "end_clarification"
        return "executor"

    def _route_after_reflection(self, state: RAGSubgraphState) -> Literal["planner", "end_success", "end_clarification"]:
        if not state.reflection_decision:
            return "end_success"
        
        decision = state.reflection_decision.decision
        if decision == "replan":
            return "planner"
        elif decision == "clarification":
            return "end_clarification"
        else:
            return "end_success"

    async def _finalize_node(self, state: RAGSubgraphState) -> Dict[str, Any]:
        status = "success"
        clarification_question = None
        
        all_contexts = list(state.history) + list(state.step_outputs)


        if state.reflection_decision and state.reflection_decision.decision == "clarification":
            status = "clarification"
            clarification_question = state.reflection_decision.clarification_question
        elif state.planner_output and state.planner_output.status == "clarification":
            status = "clarification"
            clarification_question = state.planner_output.clarification_question
            
        return {
            "retriving_results": RAGSubgraphOutput(
                status=status,
                contexts=all_contexts,
                clarification_question=clarification_question
            )
        }


def build_rag_subgraph(
    lc_openai_client: LCOpenAI,
    settings: Settings,
    vdb_tools: VDBTools,
    mongodb_tools: MongoDBTools,
    sql_tools: SQLTools,
) -> Any:
    subgraph = RAGSubgraph(
        lc_openai_client=lc_openai_client,
        settings=settings,
        vdb_tools=vdb_tools,
        mongodb_tools=mongodb_tools,
        sql_tools=sql_tools,
    )
    return subgraph.graph



