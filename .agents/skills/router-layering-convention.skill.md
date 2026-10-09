---
name: router-layering-convention
description: "Use when creating or reviewing FastAPI routers. Enforces thin router pattern: HTTP only, no business logic, Pydantic DTOs, and dependency injection via Depends()."
---

# Router Layering Convention Skill

## Purpose

Defines the canonical thin-router pattern for FastAPI route handlers in this project. Routers handle HTTP mechanics and delegate immediately to services or orchestrators — nothing more. Grounded in `src/routers/assistant_router.py` and `src/routers/lecture_router.py`.

## When To Use

- Adding a new API endpoint.
- Reviewing a router for business logic leakage.
- Migrating logic from router to service layer.

---

## Rule 1: Router Structure

```python
# src/routers/<feature>_router.py
from fastapi import APIRouter, Depends, Path, Query
from helpers.logger import get_logger
from schemas import MyRequestDTO, MyResponseDTO
from services.my_feature.my_feature_service import MyFeatureService
from core.request_dependencies import get_my_feature_service

logger = get_logger(__name__)

my_feature_route = APIRouter(
    prefix="/my-feature",
    tags=["MyFeature"],
)


@my_feature_route.post(
    "/action/{resource_id}",
    summary="Short action description",
    description="Longer description for API docs.",
    response_model=MyResponseDTO,
)
async def do_action(
    resource_id: str = Path(..., description="The resource identifier."),
    payload: MyRequestDTO = ...,
    service: MyFeatureService = Depends(get_my_feature_service),
) -> MyResponseDTO:
    return await service.do_action(payload, resource_id)
```

**Rules:**
- Router function body is typically **1-3 lines** — receive input, call service, return result.
- NO business logic in routers (no if/else for domain rules, no calculations).
- NO database calls from routers.
- NO exception handling/translation in routers — let the central exception handler do that.
- The only allowed multi-line logic: serialization edge cases (e.g., `json.dumps` with `ensure_ascii=False` for Unicode safety).

---

## Rule 2: Dependency Injection

All services are injected via `Depends()`:

```python
# CORRECT
async def chat(
    service: ChatbotService = Depends(get_chatbot_service),
): ...

# WRONG — accessing app.state directly in router
async def chat(request: Request): ...
    service = request.app.state.chatbot_service  # ← violates DI pattern
```

Dependency getter functions live in `src/core/request_dependencies.py`:

```python
# src/core/request_dependencies.py
from fastapi import Request

def get_chatbot_service(request: Request):
    return request.app.state.chatbot_service

def get_lecture_orchestrator(request: Request):
    return request.app.state.lecture_orchestrator
```

---

## Rule 3: Request & Response DTOs

All input and output shapes are Pydantic models defined in `src/schemas/`:

```python
# src/schemas/my_feature_schema.py
from pydantic import BaseModel, Field

class MyRequestDTO(BaseModel):
    message: str = Field(..., max_length=1000)
    level:   int = Field(..., ge=0, le=2)

class MyResponseDTO(BaseModel):
    result:  str
    details: dict = {}
```

**Rules:**
- Schema-level validation (max_length, ge, le, required fields) lives in Pydantic models.
- Do NOT duplicate schema validation in service layer.
- Response models are always `response_model=MyResponseDTO` in the decorator.
- Schemas live in `src/schemas/<feature>_schema.py`, imported by both routers and services.

---

## Rule 4: Router Registration

All routers are registered in `src/main.py` via `app.include_router`:

```python
# src/routers/__init__.py — export the route object
from .my_feature_router import my_feature_route

# src/main.py
from routers import my_feature_route
app.include_router(my_feature_route)
```

---

## Rule 5: When to Route to Orchestrator vs. Service

| Use Case | Delegate to |
|---|---|
| Single feature operation (create, get, summarize) | Service directly |
| Multi-step cross-service workflow (upload → parse → embed → store) | Orchestrator |
| AI chat (graph invocation + session + background tasks) | Service (ChatbotService wraps the complexity) |

Routers delegate to orchestrators when the route is explicitly a "workflow trigger" endpoint, not a resource operation.

---

## Review Checklist

- Is the route handler 1-3 lines long (excluding typing/docs)?
- Does the handler delegate immediately to a service or orchestrator?
- Are all services injected via `Depends(get_*)`, not `request.app.state`?
- Are request/response shapes Pydantic models from `src/schemas/`?
- Is there any domain logic or DB calls in the router? (There should be none.)
- Is the router registered in `__init__.py` and included in `main.py`?
