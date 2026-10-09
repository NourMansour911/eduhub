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
- Prefer `src/services/<feature>/chains/<feature>_chain.py` for graph-based features.
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
- For chains that need both parsed output AND token usage (e.g. background chains), use `.with_structured_output(..., include_raw=True)` and extract usage from `raw_result.get("raw")`.

### 6) LCOpenAI Wrapper
- This project uses `LCOpenAI` (from `integrations.llm`) as a wrapper around `ChatOpenAI`.
- Build the `ChatOpenAI` instance by calling `lc_openai_client.get_langchain_llm(model=..., temperature=...)`.
- Pass the resulting `ChatOpenAI` instance into chain builders — never import or instantiate `ChatOpenAI` directly in chain files.

### 7) LangSmith Tracing
- All chain `.ainvoke()` calls MUST include a `config={"run_name": "..."}` parameter for LangSmith trace naming.
- LangSmith is configured globally in `main.py` via `os.environ["LANGCHAIN_TRACING_V2"]` — no per-chain tracing setup needed.
- Use descriptive `run_name` strings: `"Update Session Summary Chain"`, `"Update Student Persona Chain"`.

### 8) Integration with Services
- Services may call chain builders, but services should own the workflow decision.
- The chain should not know about HTTP, Redis, repositories, or repositories.
- If the flow needs multiple service calls, keep that in a service or orchestrator, not in the chain.

### 9) Reuse Pattern
- Reuse the same chain module for the same feature flow.
- Do not duplicate prompt formatting in multiple services.
- If the chain becomes feature-wide, expose it through the feature package `__init__.py` only when useful.

## Recommended File Layout

- `src/services/<feature>/chains/<feature>_chain.py`   ← preferred for graph-based features
- `src/services/<feature>/<feature>_chain.py`          ← acceptable for simple single-file services
- `src/services/<feature>/<feature>_service.py`
- `src/services/<feature>/__init__.py`

## Example Pattern: Simple String Chain

```python
from typing import Any, Dict
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

SYSTEM_TMPL = """
Write a compact summary using only the provided text.
"""

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_TMPL),
    ("human", "Text:\n{text}\n"),
])


def build_summary_chain(llm: ChatOpenAI) -> Runnable:
    def prepare_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        text = (inputs.get("text") or "").strip()
        if not text:
            raise ValueError("text is required")
        return {"text": text}

    return RunnableLambda(prepare_input) | PROMPT | llm | StrOutputParser()


# Usage in service:
# result = await self.summary_chain.ainvoke(
#     {"text": content},
#     config={"run_name": "Summarize Chain Run"}
# )
```

## Example Pattern: Structured Output Chain

```python
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


class PersonaUpdateDecision(BaseModel):
    should_update:   bool  = Field(..., description="True if persona needs updating.")
    updated_persona: str   = Field(..., description="Updated persona text.")


SYSTEM_PROMPT = """
Analyze the conversation and determine if the student persona should be updated.
"""

DYNAMIC_TEMPLATE = """
Current Persona: {user_persona}
Recent Messages: {messages_history}
User Query: {user_query}
"""


def build_persona_chain(llm: ChatOpenAI):
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", DYNAMIC_TEMPLATE),
    ])
    return prompt | llm.with_structured_output(PersonaUpdateDecision)

# Usage:
# decision = await self.persona_chain.ainvoke({...}, config={"run_name": "Update Persona Chain"})
# if decision.should_update:
#     collection.persona = decision.updated_persona
```

## Review Checklist

- Is the chain small and reusable?
- Is the input preparation minimal?
- Is the prompt domain-specific and clear?
- Is the output parser appropriate for the return type?
- If structured output is needed, does the chain map cleanly to a `Pydantic` model?
- Is the workflow still owned by the service layer?
- Does the chain avoid HTTP, storage, and orchestration concerns?
- Is the LLM received as a `ChatOpenAI` argument (not constructed internally)?
- Do all `.ainvoke()` calls include `config={"run_name": "..."}`?
