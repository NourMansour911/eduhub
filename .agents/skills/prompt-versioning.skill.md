---
name: prompt-versioning
description: "Use when creating, versioning, pulling, or pushing LLM prompt templates across AI projects using LangSmith Hub. Defines prompt registry structures, local fallback mechanisms, CLI push scripts, and environment tag conventions."
---

# Prompt Versioning & LangSmith Hub Skill

## Purpose

Defines the standard pattern for decoupling LLM prompt templates from Python source code by versioning them on **LangSmith Hub**, while maintaining zero-downtime local fallbacks in the codebase. Grounded in `scripts/push_prompts.py` and `LANGSMITH_PROMPT_VERSIONING_GUIDE.md`.

---

## When To Use

- Adding a new LLM node, chain, or prompt template to an AI project.
- Pushing local prompt changes to LangSmith Prompt Hub for team collaboration and version tracking.
- Loading prompts dynamically in production with fail-safe local fallback.
- Standardizing prompt management across multiple microservices or repositories.

---

## Rule 1: Prompt Structure in Code (Local Registry)

Keep system and context messages as explicit string constants on the Node or Chain class. This acts as both the **Source of Truth** for offline execution and the payload for pushing to LangSmith Hub.

```python
# src/services/<feature>/nodes/<node_name>.py
from langchain_core.prompts import ChatPromptTemplate

class MyNode:
    # 1. Define raw text constants
    SYSTEM_MSG = """You are an AI assistant..."""
    CONTEXT_MSG = """User Input: {user_input}\nContext: {context}"""

    # 2. Local fallback ChatPromptTemplate
    LOCAL_PROMPT = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_MSG),
        ("human", CONTEXT_MSG),
    ])
```

---

## Rule 2: Dynamic Prompt Loading with Local Fallback

When initializing an LLM node or chain, attempt to pull the prompt version from LangSmith Hub by repo identifier. If offline or missing API key, fall back gracefully to the local prompt template.

```python
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
import logging

logger = logging.getLogger(__name__)

def load_prompt_with_fallback(repo_identifier: str, local_prompt: ChatPromptTemplate) -> ChatPromptTemplate:
    """Pull prompt from LangSmith Hub with fail-safe local fallback."""
    try:
        remote_prompt = hub.pull(repo_identifier)
        logger.info(f"Successfully pulled prompt '{repo_identifier}' from LangSmith Hub.")
        return remote_prompt
    except Exception as exc:
        logger.warning(
            f"Failed to pull prompt '{repo_identifier}' from LangSmith Hub ({exc}). "
            f"Falling back to local codebase template."
        )
        return local_prompt
```

---

## Rule 3: Centrally Managed Push Script (`scripts/push_prompts.py`)

Every project must maintain a push script to sync all prompts to LangSmith Hub.

### Standard Script Structure:

```python
import os
import sys
from dotenv import load_dotenv
from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate

# 1. Load environment
load_dotenv(override=True)

# 2. Import node/chain prompt templates
from services.chatbot.nodes.planner import PlannerNode
from services.chatbot.nodes.answering_node import AnsweringNode

def get_all_prompts():
    return {
        "planner": {
            "description": "Planner node tool selection prompt",
            "template": ChatPromptTemplate.from_messages([
                ("system", PlannerNode.SYSTEM_MSG),
                ("human", PlannerNode.CONTEXT_MSG),
            ]),
        },
        "answering": {
            "description": "Educational mentor response prompt",
            "template": ChatPromptTemplate.from_messages([
                ("system", AnsweringNode.SYSTEM_MSG),
                ("human", AnsweringNode.CONTEXT_MSG),
            ]),
        },
    }

def push_prompts_to_langsmith():
    api_key = os.getenv("LANGSMITH_API_KEY")
    app_name = os.getenv("APP_NAME", "my-app").strip().lower()

    if not api_key:
        print("[ERROR] LANGSMITH_API_KEY not found in environment.")
        sys.exit(1)

    client = Client(api_key=api_key)
    prompts = get_all_prompts()

    for key, item in prompts.items():
        repo_name = f"{app_name}-{key}"
        print(f"[->] Pushing '{key}' as '{repo_name}'...")
        try:
            url = client.push_prompt(
                prompt_identifier=repo_name,
                object=item["template"],
                is_public=False,
                description=item["description"],
                tags=[app_name, key],
            )
            print(f"     [SUCCESS] Published: {url}")
        except Exception as exc:
            if "not changed" in str(exc) or "Nothing to commit" in str(exc):
                print(f"     [UP-TO-DATE] No changes detected on Hub.")
            else:
                print(f"     [FAILED] Error pushing '{key}': {exc}")

if __name__ == "__main__":
    push_prompts_to_langsmith()
```

---

## Rule 4: Naming & Tagging Conventions

- **Repository Identifier Pattern**: `{app_name}-{prompt_name}` (e.g., `eduhub-planner`, `eduhub-answering`).
- **Visibility**: Always set `is_public=False` for private enterprise/project prompts.
- **Tags**: Attach `[app_name, prompt_name, environment]` (e.g. `["eduhub", "planner", "staging"]`).

---

## Verification & Workflow Test

1. Run prompt push script: `python scripts/push_prompts.py`
2. Verify all prompts report `[SUCCESS]` or `[UP-TO-DATE]`.
3. Check LangSmith Hub UI under the project organization to verify commits and prompt version history.
