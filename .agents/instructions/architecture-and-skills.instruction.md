---
description: "Core backend architecture and skill routing for Python files in EduHub."
name: "Backend Architecture & Skill Router"
applyTo: "**/*.py"
---

# Backend Architecture Preferences

## 1. Core Architectural Invariants (MUST FOLLOW)
- **Layer Separation**: `Router -> Service -> Repository / Integration -> External Systems`.
- **Feature-Based Layout**: Group by features (`src/routers/`, `src/services/<feature>/`, `src/repositories/`).
- **Thin Routers**: 1–3 lines HTTP only (`Depends()`). NO business logic or DB calls in routers.
- **Services**: Own business logic, reusable, independent of HTTP.
- **Orchestrators**: Optional. Use ONLY when coordinating multiple independent services.
- **Integrations**: All external APIs (LLMs, Redis, Qdrant) MUST go through `src/integrations/`.
- **Docs & Plans Location**: All generated docs/discussions MUST go into `.agents/docs/`, and all implementation plans MUST go into `.agents/plans/` (keep repository root clean).

---

## 2. Skill Index (Use Specialized Skills for Implementation)
Load the corresponding skill from `.agents/skills/*.skill.md` when working on specific areas:

| Domain | Skill File | Trigger |
|---|---|---|
| **Graph Nodes** | `langgraph-node-builder.skill.md` | Callable-class nodes, prompts, structured output |
| **Agent Workflows** | `langgraph-agentic-workflow-builder.skill.md` | StateGraph builder, cyclic DAGs, Studio |
| **State & Data** | `workflow-state-data-exchange.skill.md` | States schema, clipping, tool deduplication |
| **Background / Eval** | `background-eval-and-session-tasks.skill.md` | Fire-and-forget telemetry, 4-layer evaluation |
| **Session Cache** | `redis-session-state-lifecycle.skill.md` | RedisSessionDTO, session state & lifecycle |
| **AI Services** | `ai-feature-service-pattern.skill.md` | AI service class, llm_map, graph wrapping |
| **App Lifecycle** | `app-lifecycle-di.skill.md` | FastAPI lifespan, app.state, request dependencies |
| **Integrations** | `provider-abstraction-factory.skill.md` | Factories, abstract interfaces, vendors |
| **Repositories** | `mongo-repository-pattern.skill.md` | Mongo repos, indexes, init_mongo_resources |
| **Routers** | `router-layering-convention.skill.md` | FastAPI thin routers, request/response DTOs |
| **Chains** | `chain-building.skill.md` | LCEL prompt chains, structured outputs |
| **Prompt Hub** | `prompt-versioning.skill.md` | LangSmith Hub decoupling & local fallbacks |
| **Exceptions** | `error-handling.skill.md` | AppException -> ServiceException hierarchy |
| **Orchestrator** | `workflow-orchestration.skill.md` | Deciding Service vs. Orchestrator |
| **Code Standards** | `coding-standards.skill.md` | Pydantic v2 typing, schemas, FailureInfo |
