---
description: "Deterministic Configuration & Fallback Policy: Strictly respect predefined configurations, fail explicitly on missing required values, and prohibit unjustified defensive fallbacks."
name: "Deterministic Configuration & Fallback Policy"
applyTo: "**/*.py"
---

# Deterministic Configuration & Fallback Policy

You must strictly respect predefined configurations, established decisions, and explicit values throughout the system.

## 1. Respect Existing Definitions

Treat explicitly provided values, configurations, constants, defaults, and previously established architectural decisions as authoritative.

Never override, reinterpret, recalculate, or replace a predefined value based on assumptions or personal judgment.

Do not introduce alternative values or fallback options when a value has already been explicitly defined.

Before proposing or implementing any value, inspect the existing codebase, configuration, and context to determine whether it is already defined.

Never duplicate an existing configuration or introduce competing sources of truth.

## 2. No Unjustified Fallbacks

Do not add defensive fallbacks such as value or default, get(key, default), try/except with silent defaults, or conditional substitutions merely to make the system appear more resilient.

Never assume that a missing value should be replaced with a guessed, generic, or previously used value.

If a required value is missing, treat it as a configuration or implementation error. Fail explicitly and report the issue.

Never silently hide missing data, invalid states, broken assumptions, or unexpected execution paths.

## 3. Business-Driven Optionality

A value may legitimately be optional ONLY when its absence is explicitly allowed by the business requirements or system design.

For genuinely optional values:

Handle their absence according to the explicitly defined business rules.

Do not invent fallback behavior beyond those rules.

Preserve the distinction between None, an empty value, a missing field, and an invalid value whenever they have different meanings.

## 4. Deterministic Decision-Making

Follow established business rules and architectural decisions exactly.

Do not create alternative execution paths, compatibility layers, recovery mechanisms, or implicit defaults unless they are explicitly required.

Do not make assumptions to resolve ambiguity in critical configuration or business logic.

If a decision cannot be determined from the available specifications or codebase, stop and request clarification instead of guessing.

## 5. Implementation Validation

Before implementing a change:

Identify the authoritative source of every relevant value and decision.

Determine whether each value is required or explicitly optional.

Reuse existing definitions instead of introducing new ones.

Fail explicitly when a required value or invariant is missing or violated.

Implement only the behavior justified by the existing requirements.

**Core Principle:** Be deterministic, not speculative. A predefined value is authoritative. A missing required value is an error, not an invitation to invent a fallback. Optionality must be justified by actual business requirements, never by convenience.
