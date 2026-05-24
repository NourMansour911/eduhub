---
name: chain-building
description: "Use when building or refactoring LangChain or LangGraph chains, prompt pipelines, runnable graphs, or feature-specific chain builders in backend Python projects."
---

# Chain Building Skill

## Purpose

Use this skill when creating or changing a chain that prepares input, builds prompts, runs an LLM, and parses output.
It also covers chains that return Pydantic models or use structured output parsers.

Keep the chain as a small reusable feature helper, not as a place for persistence or HTTP concerns.

## When To Use

Use this skill when:
- Creating a new `build_*_chain` function.
- Refactoring an existing chain module.
- Adding prompt composition for a feature service.
- Introducing `RunnableLambda`, `ChatPromptTemplate`, `Pydantic` models, or output parsers.
- Reviewing chain code for consistency and separation of concerns.

## Core Rules

### 1) Ownership
- Put the chain close to the feature that owns the behavior.
- Prefer `src/services/<feature>/<feature>_chain.py` for feature-specific chains.
- Do not put business orchestration, persistence, or router logic inside the chain builder.

### 2) Chain Shape
- Keep the chain builder pure.
- Accept only the minimal inputs needed to build the runnable.
- Use `RunnableLambda` for input shaping and lightweight validation.
- Keep prompt templates as constants near the builder.
- End the chain with the correct output parser for the returned type.
- If the chain returns structured data, prefer a `Pydantic` model or a parser that maps cleanly to it.

### 3) Input Handling
- Validate only the input the chain truly depends on.
- Raise a clear error if a required chain input is missing.
- Do not repeat schema-level validation that already exists in Pydantic.
- Normalize inputs before the prompt stage.

### 4) Prompt Rules
- Keep system prompts focused and domain-specific.
- Keep user prompts short and explicit.
- Avoid hidden assumptions in prompt text.
- Do not mix unrelated feature logic into one prompt.

### 5) Structured Output
- Use structured output when the caller needs a typed response.
- Align the chain output with the feature schema or `Pydantic` model that consumes it.
- Choose the simplest parser that matches the expected response shape.

### 6) Integration with Services
- Services may call chain builders, but services should own the workflow decision.
- The chain should not know about HTTP, Redis, repositories, or repositories.
- If the flow needs multiple service calls, keep that in a service or orchestrator, not in the chain.

### 7) Reuse Pattern
- Reuse the same chain module for the same feature flow.
- Do not duplicate prompt formatting in multiple services.
- If the chain becomes feature-wide, expose it through the feature package `__init__.py` only when useful.

## Recommended File Layout

- `src/services/<feature>/<feature>_chain.py`
- `src/services/<feature>/<feature>_service.py`
- `src/services/<feature>/__init__.py`

## Example Pattern

```python
from typing import Any, Dict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

SYSTEM_TMPL = """
Write a compact summary using only the provided text.
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_TMPL),
        ("human", "Text:\n{text}\n"),
    ]
)


def build_example_chain(llm: ChatOpenAI) -> Runnable:
    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        text = (inputs.get("text") or "").strip()
        if not text:
            raise ValueError("text is required")
        return {"text": text}

    return RunnableLambda(prepare_input) | PROMPT | llm | StrOutputParser()
```

## Review Checklist

- Is the chain small and reusable?
- Is the input preparation minimal?
- Is the prompt domain-specific and clear?
- Is the output parser appropriate for the return type?
- If structured output is needed, does the chain map cleanly to a `Pydantic` model?
- Is the workflow still owned by the service layer?
- Does the chain avoid HTTP, storage, and orchestration concerns?
