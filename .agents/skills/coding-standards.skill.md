---
name: coding-standards
description: "General Python coding standards: Pydantic v2 strict typing, composition over inheritance, avoiding redundant type checks, centralized schemas, and FailureInfo pattern."
---

# Coding Standards & Python Best Practices Skill

## Purpose
Defines project-wide Python coding conventions, strict typing rules, schema organization, and failure handling patterns for EduHub.

## When To Use
- Writing or refactoring any Python functions, classes, or modules.
- Creating state models, DTOs, or schema classes.
- Handling workflow errors and tool outcomes without throwing raw exceptions.

---

## 1. Strict Typing & Pydantic v2

- **Mandatory Pydantic v2**: Use Pydantic v2 `BaseModel` for all state, payload, and tool output structures.
- **Avoid Redundant `isinstance`**: Trust declared type hints and function contracts. Do not perform excessive `isinstance` checks if types are already enforced by Pydantic or static typing.
- **Explicit Field Types**: Use explicit typing (`str`, `int`, `Optional[...]`, `List[...]`, `Dict[...]`).

```python
from typing import Optional, List
from pydantic import BaseModel, Field

class StepPayload(BaseModel):
    step_id: str = Field(..., description="Unique step identifier")
    items: List[str] = Field(default_factory=list)
    metadata: Optional[dict] = None
```

---

## 2. Centralized Schemas & Circular Import Prevention

- **Single Source of Truth**: Keep shared state models, DTOs, and graph exchange schemas in a centralized `states.py` or `schemas.py`.
- **No Circular Imports**: Cross-cutting nodes or services must import schemas from `states.py` or `dtos/`, never from each other.

---

## 3. Function & Class Design

- **Small & Focused**: Functions should perform one single logical task.
- **Composition over Inheritance**: Favor dependency injection and composable components over deep inheritance hierarchies.
- **Consistent Naming**: Use snake_case for functions/variables, PascalCase for classes, and UPPER_CASE for constants.

---

## 4. Failure Info Pattern (Non-Exception Workflow Outcomes)

- **Do NOT use numeric status codes** (e.g., 200, 404, 500) inside internal service or graph step outputs.
- **Use `FailureInfo`**: Provide a `failure_info: Optional[FailureInfo] = None` field.
  - A non-None `failure_info` indicates execution failure or clarification need.
  - Tools should return graceful `StepOutput` with `failure_info` rather than crashing graph execution.

```python
from pydantic import BaseModel
from typing import Optional

class FailureInfo(BaseModel):
    message: str
    clarification_message: Optional[str] = None
    explanation: Optional[str] = None

class StepOutput(BaseModel):
    step_id: str
    content: dict = Field(default_factory=dict)
    failure_info: Optional[FailureInfo] = None
```
