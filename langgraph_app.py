from src.core import get_settings
from src.integrations.llm import LCOpenAI
from src.services.chatbot.agents.rag import build_rag_subgraph


settings = get_settings()
lc_openai_client = LCOpenAI(
    api_key=settings.OPENAI_API_KEY,
    api_url=settings.OPENAI_API_URL,
)

chatbot_graph = build_rag_subgraph(
    lc_openai_client=lc_openai_client,
    settings=settings,
)

graph = chatbot_graph