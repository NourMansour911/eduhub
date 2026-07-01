import json
from typing import Any, Dict, Literal
from langgraph.graph import StateGraph, END, START
from langchain_openai import ChatOpenAI
from integrations.llm import LCOpenAI
from integrations.redis_provider import RedisProvider

from .states import RAGSubgraphState, RAGSubgraphOutput
from .nodes.planner import PlannerNode
from .nodes.executer import ExecutorNode
from .nodes.reflection import ReflectionNode
from core import Settings
from helpers.logger import get_chatbot_logger
from services.chatbot.agents.rag.retrieving.vdb.vdb_tools import VDBTools
from services.chatbot.agents.rag.retrieving.mongo.mongodb_tools import MongoDBTools
from services.chatbot.agents.rag.retrieving.sql.sql_tools import SQLTools
from services.chatbot.utils import extract_clean_content_text,  deduplicate_tool_outputs

logger = get_chatbot_logger(__name__)


class RAGSubgraph:
    def __init__(
        self,
        lc_openai_client: LCOpenAI,
        settings: Settings,
        vdb_tools: VDBTools,
        mongodb_tools: MongoDBTools,
        sql_tools: SQLTools,
        redis_provider: RedisProvider,
    ):
        self.redis_provider = redis_provider

        rag_llm_map: Dict[str, ChatOpenAI] = {
            # Planner needs to reason and generate structured DAG plans — slightly creative
            "planner": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.1, max_tokens=1000
            ),
            # Reflection is a binary classifier — deterministic
            "reflection": lc_openai_client.get_langchain_llm(
                model=settings.GENERATION_MODEL_ID, temperature=0.0, max_tokens=200
            ),
        }

        actual_tools = {
            "ask_in_specific_lecture_by_lecture_id": vdb_tools.ask_in_specific_lecture_by_lecture_id,
            "ask_in_the_whole_course_by_course_id": vdb_tools.ask_in_the_whole_course_by_course_id,
            "search_in_sessions_history": vdb_tools.search_in_sessions_history,
            "ask_in_legal_regulations": vdb_tools.ask_in_legal_regulations,

            "get_lecture_summary_by_lecture_id": mongodb_tools.get_lecture_summary_by_lecture_id,

            "get_lecture_id_by_lecture_name": sql_tools.get_lecture_id_by_lecture_name,
            "get_course_details_by_course_id": sql_tools.get_course_details_by_course_id,
            "get_all_course_lectures_by_course_id": sql_tools.get_all_course_lectures_by_course_id,
        }

        self.planner_node = PlannerNode(rag_llm_map["planner"])
        self.executor_node = ExecutorNode(tool_registry=actual_tools)
        self.reflection_node = ReflectionNode(rag_llm_map["reflection"])

        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(RAGSubgraphState)

        workflow.add_node("planner", self.planner_node)
        workflow.add_node("executor", self.executor_node)
        workflow.add_node("reflection", self.reflection_node)
        workflow.add_node("finalize_and_aggregate", self._finalize_node)

        workflow.add_edge(START, "planner")

        workflow.add_conditional_edges(
            "planner",
            self._route_after_planner,
            {
                "executor": "executor",
                "route_to_clarification": "finalize_and_aggregate",
            },
        )

        workflow.add_edge("executor", "reflection")

        workflow.add_conditional_edges(
            "reflection",
            self._route_after_reflection,
            {
                "planner": "planner",
                "route_to_success": "finalize_and_aggregate",
                "route_to_clarification": "finalize_and_aggregate",
            },
        )

        workflow.add_edge("finalize_and_aggregate", END)

        return workflow.compile(name="RAGSubgraph")

    def _route_after_planner(self, state: RAGSubgraphState) -> Literal["executor", "route_to_clarification"]:
        if not state.planner_output or state.planner_output.status == "clarification":
            return "route_to_clarification"
        return "executor"

    def _route_after_reflection(self, state: RAGSubgraphState) -> Literal["planner", "route_to_success", "route_to_clarification"]:
        if not state.reflection_decision:
            return "route_to_success"

        decision = state.reflection_decision.decision
        if decision == "replan":
            return "planner" if state.plan_attempts_count < 3 else "route_to_success"
        if decision == "clarification":
            return "route_to_clarification"
        return "route_to_success"

    async def _finalize_node(self, state: RAGSubgraphState) -> Dict[str, Any]:
        status = "success"
        clarification_question = None
        error_message = None

        
        all_raw = []
        all_raw.extend(state.past_messages_tool_outputs)
        all_raw.extend(state.past_attempts_tool_outputs)
        all_raw.extend(state.current_attempt_tool_outputs)

        filtered_contexts = [
            ctx for ctx in all_raw
            if ctx.failure_info is None or ctx.failure_info.clarification_message is not None
        ]
        unique_contexts = deduplicate_tool_outputs(filtered_contexts)

        retrieved_context_parts = []
        for ctx in unique_contexts:
            text = extract_clean_content_text(ctx.content)
            if text:
                retrieved_context_parts.append(
                    f"### Source: {ctx.source} (Tool: {ctx.tool_name or 'Unknown'})\n{text}"
                )
        retrieved_context = "\n\n".join(retrieved_context_parts)

        
        current_run_raw = []
        current_run_raw.extend(state.past_attempts_tool_outputs)
        current_run_raw.extend(state.current_attempt_tool_outputs)
        current_run_filtered = [
            ctx for ctx in current_run_raw
            if ctx.failure_info is None or ctx.failure_info.clarification_message is not None
        ]
        current_run_unique = deduplicate_tool_outputs(current_run_filtered)

        if state.plan_attempts_count >= 3 and state.reflection_decision and state.reflection_decision.decision == "replan":
            status = "clarification"
            clarification_question = "I couldn't retrieve the exact information after multiple attempts. Could you please clarify your question or provide more details?"
            error_message = "Exceeded the maximum number of plan attempts (3) without finding a satisfactory answer."
            logger.warning("RAG Subgraph replan attempts exhausted. Routing to clarification: %s", error_message)
        elif state.reflection_decision and state.reflection_decision.decision == "clarification":
            status = "clarification"
            clarification_question = state.reflection_decision.clarification_question
            if not clarification_question:
                clarification_question = "Could you please clarify your question or provide more details?"
            logger.info("RAG Subgraph requested clarification from reflection: %s", clarification_question)
        elif state.planner_output and state.planner_output.status == "clarification":
            status = "clarification"
            clarification_question = state.planner_output.clarification_question
            if not clarification_question:
                clarification_question = f"Could you please specify which course or topic you are referring to? (Your enrolled courses are: {state.student_courses})"
            logger.info("RAG Subgraph requested clarification from planner: %s", clarification_question)

        logger.info("RAG Subgraph execution concluded. Status: %s | Deduplicated sources: %d", status, len(unique_contexts))

        return {
            "retriving_results": RAGSubgraphOutput(
                status=status,
                retrieved_context=retrieved_context,
                run_step_outputs=current_run_unique,
                clarification_question=clarification_question,
                error_message=error_message,
            )
        }


def build_rag_subgraph(
    lc_openai_client: LCOpenAI,
    settings: Settings,
    vdb_tools: VDBTools,
    mongodb_tools: MongoDBTools,
    sql_tools: SQLTools,
    redis_provider: RedisProvider,
) -> Any:
    subgraph = RAGSubgraph(
        lc_openai_client=lc_openai_client,
        settings=settings,
        vdb_tools=vdb_tools,
        mongodb_tools=mongodb_tools,
        sql_tools=sql_tools,
        redis_provider=redis_provider,
    )
    return subgraph.graph
