from typing import Any, Dict, Literal
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from integrations import RedisProvider

from .states import ChatbotState
from .nodes.orchestrator_node import OrchestratorNode
from .nodes.rag_node import RAGNode
from .nodes.answering_node import AnsweringNode


class ChatbotGraph:
    def __init__(
        self,
        llm_map: Dict[str, ChatOpenAI],
        rag_subgraph: Any,
        redis_provider: RedisProvider,
    ):
        self.orchestrator = OrchestratorNode(llm_map["orchestrator"])
        self.rag_node = RAGNode(rag_subgraph)
        self.answering_node = AnsweringNode(
            llm_map=llm_map,
            redis_provider=redis_provider,
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ChatbotState)

        workflow.add_node("orchestrator", self.orchestrator)
        workflow.add_node("rag_node", self.rag_node)
        workflow.add_node("answering", self.answering_node)

        workflow.add_edge(START, "orchestrator")
        workflow.add_conditional_edges(
            "orchestrator",
            self._route_after_orchestrator,
            {
                "rag_node": "rag_node",
                "answering": "answering",
            },
        )
        workflow.add_edge("rag_node", "answering")
        workflow.add_edge("answering", END)

        return workflow.compile()

    def _route_after_orchestrator(self, state: ChatbotState) -> Literal["rag_node", "answering"]:
        if state.rag_status == "retrieve":
            return "rag_node"
        return "answering"


def build_chatbot_graph(
    llm_map: Dict[str, ChatOpenAI],
    rag_subgraph: Any,
    redis_provider: RedisProvider,
) -> Any:
    return ChatbotGraph(
        llm_map=llm_map,
        rag_subgraph=rag_subgraph,
        redis_provider=redis_provider,
    ).graph
