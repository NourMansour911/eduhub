---
description: "brainstorm, discuss design decisions, explore technical options, or plan project implementation with the AI assistant"
---

# Discuss & Project Architecture Workflow (`/discuss`)

Use this workflow when you want to brainstorm, discuss design decisions, explore technical options, or plan project implementation with the AI assistant.

This workflow automatically creates and maintains a dedicated discussion document (README/Design Doc) where ideas, architectures, trade-offs, and step-by-step implementation plans are recorded iteratively.

---

##  Workflow Objectives

1. **Structured Brainstorming**: Clarify requirements, constraints, and architecture options.
2. **Persistent Record**: Automatically create and update a Markdown document in `.agents/docs/` (or `docs/discussions/`).
3. **Actionable Roadmap**: Refine the discussion into a concrete, step-by-step implementation plan.

---

##  Step-by-Step Execution Guide for Agent

### Step 1: Identify Topic & Purpose
- Check if the user specified a topic or feature with the command (e.g., `/discuss langgraph integration`).
- If no topic was specified, ask the user to briefly describe what feature, architecture, or project topic they would like to discuss.

### Step 2: Initialize Discussion Document
Create a new dedicated Markdown file under `.agents/docs/` (or `docs/discussions/`).
- **Filename convention**: `DISCUSS_<topic_name_snake_case>.md` (e.g., `DISCUSS_langgraph_integration.md`).
- **Initial Document Template**:

```markdown
# Discussion & Implementation Plan: [Topic Name]

> **Date**: [YYYY-MM-DD]  
> **Status**: In Progress 🟡  
> **Location**: `.agents/docs/DISCUSS_[topic_name].md`

---

## 1. Executive Summary & Goals
- **Context**: Brief background on why this feature/topic is being discussed.
- **Objectives**: Primary goals and key success criteria.

## 2. Requirements & Constraints
- Functional Requirements
- Technical & System Constraints
- Dependencies

## 3. Proposed Architectures & Solutions
### Option A: [Name]
- **Overview**:
- **Pros**:
- **Cons**:

### Option B: [Name]
- **Overview**:
- **Pros**:
- **Cons**:

## 4. Key Questions & Design Decisions
- [ ] Question 1 / Decision needed
- [ ] Question 2 / Decision needed

## 5. Proposed Implementation Steps & Roadmap
1. Phase 1: Setup & Data Schemas
2. Phase 2: Core Logic
3. Phase 3: Integration & Testing

## 6. Discussion Log & Notes
- Key updates and decisions made during the session.
```

### Step 3: Interactive Discussion & Brainstorming
- Present initial ideas or analysis based on existing codebase context.
- Present architectural options with pros/cons clearly formatted.
- Ask 2-3 focused questions to resolve ambiguities or clarify design preferences.
- Optionally recommend using `/grill-me` or interactive options if choices are complex.

### Step 4: Iterative Document Updates
- As alignment is reached on design decisions, update `DISCUSS_<topic_name>.md`.
- Keep the document up to date after major milestones or decisions.
- Reflect agreed-upon options, architecture diagrams (Mermaid), API signatures, or code snippets in the document.

### Step 5: Finalization & Transition to Plan
- Once discussion concludes, update the document status to `Approved 🟢`.
- Offer to transition the final roadmap into a `/plan` execution workflow or task breakdown.
