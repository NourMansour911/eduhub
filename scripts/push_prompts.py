

import os
import sys
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
ENV_PATH = os.path.join(SRC_DIR, ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH, override=True)

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


from core.settings import get_settings


from services.chatbot.nodes.orchestrator_node import OrchestratorNode
from services.chatbot.nodes.answering_node import AnsweringNode
from services.chatbot.agents.rag.nodes.planner import PlannerNode
from services.chatbot.agents.rag.nodes.reflection import ReflectionNode
from services.chatbot.chains.summary_chain import PROMPT as SUMMARY_PROMPT
from services.chatbot.chains.persona_chain import PROMPT as PERSONA_PROMPT
from services.grading.grading_chain import GRADING_PROMPT
from services.summarize.summarize_chain import PROMPT as SUMMARIZE_PROMPT


def get_all_prompts_to_push():
    return {
        "orchestrator": {
            "description": "EduHub Router and Query Rewriter prompt for Chatbot orchestrator node",
            "template": ChatPromptTemplate.from_messages([
                ("system", OrchestratorNode.SYSTEM_MSG),
                ("human", OrchestratorNode.CONTEXT_MSG),
            ]),
        },
        "planner": {
            "description": "EduHub Cyclic DAG Planner prompt for tool planning and orchestration",
            "template": ChatPromptTemplate.from_messages([
                ("system", PlannerNode.SYSTEM_MSG),
                ("human", PlannerNode.CONTEXT_MSG),
            ]),
        },
        "reflection": {
            "description": "EduHub RAG Reflection node prompt for context quality check and replanning",
            "template": ChatPromptTemplate.from_messages([
                ("system", ReflectionNode.SYSTEM_MSG),
                ("human", ReflectionNode.CONTEXT_MSG),
            ]),
        },
        "answering": {
            "description": "EduHub Nova Socratic Educational Mentor response generation prompt",
            "template": ChatPromptTemplate.from_messages([
                ("system", AnsweringNode.SYSTEM_MSG),
                ("human", AnsweringNode.CONTEXT_MSG),
            ]),
        },
        "grading": {
            "description": "EduHub Professor exam answer auto-grading prompt",
            "template": GRADING_PROMPT,
        },
        "summarize": {
            "description": "EduHub Lecture Multi-level summarization prompt",
            "template": SUMMARIZE_PROMPT,
        },
        "session-summary": {
            "description": "EduHub Chat session running summary compaction prompt",
            "template": SUMMARY_PROMPT,
        },
        "persona": {
            "description": "EduHub Student learning persona extractor prompt",
            "template": PERSONA_PROMPT,
        },
    }


def main():
    settings = get_settings()
    api_key = settings.LANGSMITH_API_KEY
    app_name = (settings.APP_NAME or "eduhub").strip().lower()
    tag = "staging"

    if not api_key:
        print("[ERROR] LANGSMITH_API_KEY is not configured in .env file.")
        sys.exit(1)

    print("=" * 70)
    print("  EduHub LangSmith Prompt Hub Uploader")
    print(f"  Application: '{app_name}'")
    print(f"  Environment Tag: '{tag}'")
    print("=" * 70)

    client = Client(api_key=api_key)
    prompts = get_all_prompts_to_push()
    success_count = 0
    failure_count = 0

    for key, item in prompts.items():
        repo_name = f"{app_name}-{key}"

        print(f"\n[->] Pushing prompt '{key}' to '{repo_name}'...")
        try:
            url = client.push_prompt(
                prompt_identifier=repo_name,
                object=item["template"],
                is_public=False,
                description=item["description"],
                tags=[app_name, key, tag],
                
            )
            print(f"     [SUCCESS] Published to: {url}")
            success_count += 1
        except Exception as exc:
            if "Nothing to commit" in str(exc) or "not changed since latest commit" in str(exc):
                print(f"     [UP-TO-DATE] Prompt is already up to date on LangSmith Hub.")
                success_count += 1
            else:
                print(f"     [FAILED] Error pushing '{key}': {exc}")
                failure_count += 1

    print("\n" + "=" * 70)
    print(f"  Summary: {success_count} succeeded, {failure_count} failed out of {len(prompts)} total prompts.")
    print("=" * 70)


if __name__ == "__main__":
    main()
