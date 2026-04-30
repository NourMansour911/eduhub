---
description: "Use when creating, modifying, reviewing, or refactoring backend Python code, APIs, workflows, integrations, and architecture decisions. Enforces layered design and strict separation of concerns."
name: "Global Backend Architecture Preferences"
applyTo: "**/*.py"
---

# Global Backend Architecture Preferences (MUST FOLLOW)

This project follows a backend design style based on a consistent engineering architecture pattern used across previous systems.

These instructions define how code should be structured, not business logic details.

## 1. Core Architecture Principle

All backend systems MUST follow a layered and modular architecture:

Router -> Orchestrator -> Service -> Repository / Integration -> External Systems

This separation is mandatory for maintainability and scalability.

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
- Delegates all logic to orchestrators
- MUST remain thin

### Orchestrator Layer

- Coordinates multi-step workflows
- Combines multiple services
- Defines business use-case flows
- Keeps routers clean

### Service Layer

- Core business logic
- Reusable across multiple workflows
- Independent from HTTP and persistence

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

- Complex flows MUST go through orchestrators
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

## 8. Copilot Behavior Expectation

When generating code, Copilot MUST:

- Follow this architecture strictly
- Respect separation of layers
- Reuse existing patterns instead of inventing new ones
- Keep code consistent with current project structure