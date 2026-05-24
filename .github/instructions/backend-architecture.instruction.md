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
- Use the project structure and the active instruction files together when deciding the right primitive.
- Repo skills live in `.github/skills/*.skill.md`.
- User-level skills live in the VS Code user prompts folder, but project work should prefer repo skills first.
- For chain/prompt/runnable work, check for a matching skill before inventing a new pattern.

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

- Keep functions small and focused
- Prefer composition over inheritance
- Avoid duplication across modules
- Maintain consistent naming across features
- Keep architecture predictable across the project

## 7. Architecture Consistency Rule

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