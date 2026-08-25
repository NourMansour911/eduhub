---
description: "Use when creating, modifying, reviewing, or refactoring backend Python code, APIs, workflows, integrations, and architecture decisions. Enforces layered design and strict separation of concerns."
name: "Global Backend Architecture Preferences"
applyTo: "**/*.py"
---

# Global Backend Architecture Preferences (MUST FOLLOW)

This project follows a practical backend style based on the existing eduhub codebase.

These instructions define how code should be structured, not business logic details.

## 0. Skill Awareness

- If a task clearly matches a specialized skill, use that skill-guided workflow instead of guessing.
- Skills are for focused workflows and edge cases; do not ignore them when the task fits.
- Repo skills live in `.agent/skills/*.skill.md`.
- User-level skills live in VS Code user prompts, but project work should prefer repo skills first.

### 12-Skill Index

#### Group A: LangGraph & Agentic Patterns

| Skill File | Description | Activate When |
|---|---|---|
| `langgraph-node-builder.skill.md` | **PRIMARY**. Callable-class node pattern: `__init__` chain setup, `async __call__` delta return, static/dynamic prompt separation, structured output with `include_raw=True`, telemetry extraction, short-circuit guards. | Creating or reviewing ANY LangGraph node. |
| `langgraph-agentic-workflow-builder.skill.md` | `StateGraph` builder class, cyclic DAG (Planner→Executor→Reflection), nested subgraph wrapping, LangGraph Studio `studio.py`. | Building a new graph, adding cyclic routing, or compiling for Studio. |
| `workflow-state-data-exchange.skill.md` | Centralized `states.py` design, `StepOutput` schema, message clipping (500 chars / last 6), tool output deduplication by `(tool_name, tool_args)`, format utilities. | Designing state schemas, handling message history, managing tool results. |

#### Group B: Session, Background & Evaluation

| Skill File | Description | Activate When |
|---|---|---|
| `background-eval-and-session-tasks.skill.md` | `asyncio.create_task` fire-and-forget, 4-layer telemetry (`RequestLayer`, `RetrievalLayer`, `GenerationLayer`, `PerformanceLayer`), thresholded summary/persona updates (threshold: 6 messages). | Adding background tasks, evaluation pipelines, or thresholded triggers. |
| `redis-session-state-lifecycle.skill.md` | `RedisSessionDTO`, Redis key schema (`user:{id}:session:{id}`), Redis-first caching with DB fallback, session start/chat/end lifecycle. | Implementing stateful AI sessions or Redis-backed caching. |

#### Group C: Service & Architecture Layers

| Skill File | Description | Activate When |
|---|---|---|
| `ai-feature-service-pattern.skill.md` | AI service class structure: `llm_map` construction, graph invocation with error wrapping, Redis load/save, background task dispatch, domain exception hierarchy. | Building or extending an AI-powered feature service. |
| `app-lifecycle-di.skill.md` | FastAPI lifespan context manager, startup ordering (providers → repos → services → orchestrators), `app.state` singletons, `request_dependencies.py` getters. | Modifying app startup, adding new singletons, or creating dependency getters. |
| `provider-abstraction-factory.skill.md` | Abstract base class + concrete vendor implementation + factory class. Directory: `src/integrations/<category>/`. Return interface types from factories. | Adding a new external vendor or reviewing integration boundary violations. |
| `mongo-repository-pattern.skill.md` | `create_instance` + `init_collection` + `get_indexes` pattern, `DBEnum` collection names, `init_mongo_resources` bootstrap registration, query encapsulation. | Creating or modifying a MongoDB repository. |
| `router-layering-convention.skill.md` | Thin router: 1-3 line handlers, all services via `Depends()`, Pydantic DTOs in `src/schemas/`, no domain logic. | Creating a new API route or reviewing for business logic leakage. |

#### Group D: Cross-Cutting Patterns

| Skill File | Description | Activate When |
|---|---|---|
| `chain-building.skill.md` | LCEL chain builders, `LCOpenAI` wrapper, structured output, `run_name` for LangSmith tracing, background chain patterns. | Creating or reviewing LangChain chains or prompt pipelines. |
| `error-handling.skill.md` | `AppException` → `ServiceException` → domain exception hierarchy, `status_code` + `error_code`, logging conventions, no schema-level validation duplication. | Adding exceptions, reviewing service error paths. |
| `workflow-orchestration.skill.md` | Service vs. Orchestrator decision table, `LectureOrchestrator` as the canonical cross-service coordination example. | Deciding whether a new flow needs an orchestrator or can stay in a service. |


## 1. Core Architecture Principle

All backend systems MUST follow a layered and modular architecture, but only as far as the use case needs:

Router -> Service -> Repository / Integration -> External Systems

This separation is mandatory for maintainability and scalability.

Orchestrator is optional and should be introduced only when the flow needs coordination across multiple services or multiple same-level steps.

## 2. Design Philosophy

The system is designed around:

- Separation of concerns
- Feature-based modular structure
- Clear responsibility boundaries
- Reusability of business logic
- Isolation of external dependencies

## 3. Layer Responsibilities

### Router Layer

- Handles HTTP only
- Input validation
- Dependency injection
- Delegates to orchestrators only when the route is coordinating a workflow
- Otherwise delegates directly to the service layer
- MUST remain thin

### Orchestrator Layer

- Optional workflow coordinator
- Use only when one use case must call multiple services or integrate multiple same-level business steps
- Combines services without becoming a new business layer
- Keeps routers clean when workflow composition is non-trivial

### Service Layer

- Core business logic
- Reusable across multiple workflows
- Independent from HTTP and persistence
- Preferred default boundary for most features

### Repository Layer

- Data persistence only
- No business logic
- Database abstraction layer

### Integration Layer

- External systems abstraction:
	- LLMs
	- Redis
	- Vector DBs
	- Third-party APIs
- Must isolate vendor-specific implementations

## 4. Feature-Based Structure

Code SHOULD be organized by features, not by technical layers alone.

Each feature module can contain:

- controller/router
- service
- repository
- dto/schema
- internal helpers

## 5. Workflow Rules

- Orchestrators are not the default
- Use orchestrators only when the use case has clear cross-service coordination needs
- If a flow can stay inside one service, keep it there
- If the logic needs multiple services at the same level, promote that flow to an orchestrator
- Services SHOULD be reusable and composable
- No business logic inside routers
- No direct external calls from services without integration layer

## 6. General Coding Rules

- Keep functions small and focused.
- Prefer composition over inheritance.
- **Strict Typing**: Use Pydantic v2 Models for all state and output objects.
- **Avoid Redundant Type Checks**: Trust type hints and provided contracts; do NOT use `isinstance` excessively when types are already declared in the flow.
- **Centralized Schemas**: In complex graphs or workflows, keep shared state models in a centralized `states.py` or `schemas.py` to prevent circular imports.
- Maintain consistent naming across features.

## 7. Advanced Workflow & Failure Management (e.g., LangGraph/RAG)

- **Failure Info Pattern**: Do NOT use numeric status codes for success/failure. Instead, use a `failure_info: Optional[FailureInfo]` field. A non-None `failure_info` indicates failure.
- **Graceful Tool Failures**: Tools should return a success object with `failure_info` rather than throwing raw exceptions unless the error is catastrophic.


## 8. Architecture Consistency Rule

Any new feature added MUST follow existing structure patterns.

Do NOT introduce new architectural styles inside this project.

Prefer the lightest correct abstraction for the feature as it exists in this repository.

## 8. Copilot Behavior Expectation

When generating code, Copilot MUST:

- Follow this architecture strictly
- Respect separation of layers
- Reuse existing patterns instead of inventing new ones
- Keep code consistent with current project structure
- Treat orchestrators as intentional workflow coordinators, not as a mandatory default
