---
name: workflow-orchestration
description: "Guidelines for when and how to introduce orchestrators and coordinate multi-service workflows at repo level."
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
- Provide `get_<feature>_orchestrator` for DI in routers.

## Review Checklist

- Does the flow legitimately require coordination across services?
- Are business rules kept in services and not in the orchestrator?
- Are orchestration failures handled and logged consistently?
- Are orchestrator inputs and outputs typed and documented?
