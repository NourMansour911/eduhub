from typing import  Dict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.graph.state import CompiledStateGraph
from integrations.redis_provider import RedisProvider

from .states import ChatbotState
from .nodes.rag_node import RAGNode
from .nodes.answering_node import AnsweringNode


class ChatbotGraph:
    def __init__(
        self,
        llm_map: Dict[str, ChatOpenAI],
        rag_subgraph: CompiledStateGraph,
        redis_provider: RedisProvider,
    ):
        self.rag_node = RAGNode(rag_subgraph)
        self.answering_node = AnsweringNode(
            llm_map=llm_map,
            redis_provider=redis_provider,
        )
        self.rag_subgraph = rag_subgraph
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ChatbotState)

        workflow.add_node("rag_node", self.rag_node)
        workflow.add_node("answering", self.answering_node)

        workflow.add_edge(START, "rag_node")
        workflow.add_edge("rag_node", "answering")
        workflow.add_edge("answering", END)

        return workflow.compile()



def build_chatbot_graph(
    llm_map: Dict[str, ChatOpenAI],
    rag_subgraph: CompiledStateGraph,
    redis_provider: RedisProvider,
) -> CompiledStateGraph:
    return ChatbotGraph(
        llm_map=llm_map,
        rag_subgraph=rag_subgraph,
        redis_provider=redis_provider,
    ).graph
