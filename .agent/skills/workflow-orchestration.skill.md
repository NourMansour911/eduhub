---
name: workflow-orchestration
description: "Guidelines for when and how to introduce orchestrators and coordinate multi-service workflows at repo level. Defines the boundary between Service and Orchestrator layers."
---

# Workflow Orchestration Skill

## Purpose

Define when an orchestrator is appropriate and how it should coordinate services without absorbing business logic.

## When To Use

- Creating a new cross-service use case that must call multiple services.
- Refactoring repeated multi-step flows currently implemented inside services or routers.
- Reviewing code for unnecessary orchestrator introduction.

## Core Rules

1) Intentional Use
- Introduce an orchestrator only when the flow needs to coordinate multiple services at the same level or perform non-trivial composition.
- Do not add orchestrators by default; prefer service-level implementations unless orchestration clearly simplifies the workflow.

2) Responsibilities
- Orchestrators compose services, handle parallel tasks, error aggregation, and compensation logic.
- Orchestrators do NOT contain core business rules or persistence logic; those stay in services/repositories.

3) API Shape
- Orchestrators expose coarse-grained methods representing use-cases (e.g., `store_lecture_with_summaries`).
- Keep orchestrator method inputs strongly typed (Pydantic DTOs or typed dataclasses).

4) Failure Handling
- Orchestrators should orchestrate retries, fallbacks, and rollbacks when multiple services must agree on the outcome.
- Log orchestration context and metadata; bubble domain errors upward as domain-specific ServiceExceptions.

5) Testing
- Unit-test orchestrators by mocking underlying services; ensure orchestration logic behavior is deterministic.

## Recommended Layout

- `src/orchestrators/<feature>_orchestrator.py`
- Provide `get_<feature>_orchestrator` as a request dependency in `src/core/request_dependencies.py`.

## Real Example: LectureOrchestrator

The `LectureOrchestrator` is the canonical example in this codebase.
It coordinates: `LectureService` (parse + store) → `SummarizeService` (generate summaries) → `VDBService` (embed + store in vector DB) → `EmbeddingClient` (generate embeddings).

All four steps must run in order for a single use-case ("store a lecture with its summaries and embeddings"). None of them can be collapsed into a single service, so an orchestrator is justified.

```python
# src/orchestrators/lecture_orchestrator.py
class LectureOrchestrator:
    def __init__(
        self,
        lecture_service: LectureService,
        summarize_service: SummarizeService,
        vdb_service: VDBService,
        embedding_client: Any,
    ):
        self.lecture_service   = lecture_service
        self.summarize_service = summarize_service
        self.vdb_service       = vdb_service
        self.embedding_client  = embedding_client

    async def store_lecture_with_summaries(
        self, lecture_dto: StoreLectureDTO
    ) -> StoreLectureResponse:
        # Step 1: Parse and persist to MongoDB
        lecture = await self.lecture_service.parse_and_store(lecture_dto)

        # Step 2: Generate summaries
        summaries = await self.summarize_service.generate_all_levels(lecture.lecture_id)

        # Step 3: Embed chunks and store in Vector DB
        embeddings = await self.embedding_client.embed_batch(lecture.chunks)
        await self.vdb_service.store_lecture_chunks(lecture, embeddings)

        return StoreLectureResponse(lecture_id=lecture.lecture_id, summaries=summaries)
```

## Service vs. Orchestrator Decision Table

| Scenario | Use |
|---|---|
| Single feature operation (get, update, delete) | Service |
| AI graph invocation + Redis session + background tasks | Service (wraps complexity) |
| Multi-step pipeline requiring N separate services in strict order | Orchestrator |
| Cross-service rollback / compensation logic | Orchestrator |
| One service calling another service internally | Service (composition, no orchestrator needed) |

## Review Checklist

- Does the flow legitimately require coordination across 2+ independent services?
- Are business rules kept in services and not in the orchestrator?
- Are orchestration failures handled and logged consistently?
- Are orchestrator inputs and outputs typed (Pydantic DTOs)?
- Is the orchestrator registered on `app.state` and exposed via a dependency getter?
