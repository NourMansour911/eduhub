# EduHub Backend System

EduHub is a university portal and educational platform designed to streamline course content delivery, student tracking, and automated evaluation. This repository contains the backend systems, with a focus on advanced AI orchestration, automated grading, dynamic summarization, and cognitive retrieval.

---

## Project Overview and Core Services

The backend follows a modular, asynchronous architecture. I was responsible for designing, implementing, and optimizing the following key backend services:

- **Chatbot Service**: A stateful tutoring assistant driven by LangGraph, coordinating session histories, student persona adaptivity, and a self-correcting retrieval loop.
- **Lecture Storage Pipeline**: An asynchronous ETL orchestrator utilizing Azure AI Document Intelligence for PDF parsing, text chunking, and embedding generation, storing vectors in Qdrant with hybrid indexing while cataloging metadata.
- **Grading Service**: A batch essay-grading engine that pulls questions and reference answers from MongoDB and runs concurrent evaluation chains via LangChain's batching APIs against defined thresholds.
- **Summarization Service**: An LLM-powered multi-level summary generator that structures parsed lecture notes into different detail levels for students.

---

## Technical Architecture

### 1. Chatbot: Cyclic DAG Agentic RAG

The tutoring chatbot is implemented as a stateful agent using LangGraph. It is designed to overcome the limitations of naive linear RAG and sequential tool-calling bottlenecks:

- **Cyclic Control Flow**: Built as a cyclic graph (Planner -> Executor -> Reflector -> Planner/Finalize) allowing the system to self-correct and replan dynamically.
- **Upfront DAG Planning**: Instead of a slow sequential loop where the LLM calls one tool at a time, the Planner node analyzes the request and produces a complete Directed Acyclic Graph (DAG) of steps with dependencies (e.g., Step 2 depends on the output of Step 1).
- **Parallel Multi-tasking Tool Execution**: The Executor node executes all independent steps concurrently using Python's `asyncio.gather`. By executing multiple search tools at once, the system bypasses the step-by-step LLM bottleneck, reducing latency and execution times.
- **Reflection and Self-Correction**: The Reflector node evaluates retrieved information. If it detects failure or missing data, it triggers a replan loop, feeding the failure logs back to the Planner (capped at a safety limit of 2 attempts) to dynamically try a different retrieval strategy.

### 2. Advanced Retrieval and Search Service (Vector DB Techniques)

The vector retrieval layer implements advanced search techniques to maximize context relevance:

- **Hybrid Search**: Combines semantic vector search (dense embeddings) and keyword-based search (BM25 sparse vectors) to leverage both conceptual semantics and exact keyword matches.
- **Reciprocal Rank Fusion (RRF)**: Merges sparse and dense search results using reciprocal rank scoring (using a formula of `1 / (60 + rank)`). A weighted combination (0.7 for semantic, 0.3 for keyword) is applied to produce a single deduplicated candidate list.
- **Cohere Cross-Encoder Reranking**: Integrates Cohere's advanced reranking model (`rerank-english-v3.0`) to re-score retrieved candidate documents against the original query, ensuring highly relevant passages are prioritized.
- **Query Rewriting and Multi-Query Expansion**: Uses an LLM-powered query expansion chain to generate multiple search variations from the user query. It retrieves context for all variations in parallel, fusing the results via RRF to capture multi-faceted intent.

### 3. Student Persona and Session History

- **Student Persona**: Tracks student interaction history, query complexity, and knowledge levels cached dynamically in Redis. The persona is updated inline using an async tool callback and persisted back to MongoDB at session end to tailor responses.
- **Session History Search**: indexes past conversational turns semantically in Qdrant, enabling the retrieval node to reference historical session context across chat boundaries.

### 4. Structure-Aware PDF Extraction

- **Azure AI Document Intelligence**: Parsed PDF lectures are extracted preserving structure, section headers, tables, and paragraphs. This structure-aware chunking ensures semantic context is maintained instead of relying on naive character-count cuts.

---

## Codebase Architecture and Modularity

The codebase is highly modular, prioritizing reusability and clean separation of concerns:

- **Integrations**: Generic wrapper interfaces for databases, caches, and AI models (Qdrant, Redis, MongoDB, OpenAI API), shielding business logic from SDK implementation details.
- **Repositories**: Dedicated schemas and database queries (e.g., `LectureRepo`, `AnswerRepo`), managing database collections in isolation.
- **Services**: Pure business logic modules (e.g., `LectureService`, `GradingService`, `ChatbotService`) which perform data manipulation and coordination.
- **Orchestrators**: Higher-level service managers (e.g., `LectureOrchestrator`) that chain business logic across multiple services.
- **LangGraph Agents**: Graph nodes, routers, and state definitions (e.g., `RAGSubgraphState`) separating flow execution from backend services.

### Infrastructure and CI/CD

- **Dockerization**: The entire application is containerized with custom Dockerfiles and a root-level Docker Compose configuration, facilitating isolated multi-service deployments (FastAPI, Redis, MongoDB, Qdrant).
- **GitHub Actions**: An automated Continuous Integration workflow (`ci.yml`) executes static checks, linters, and python testing suites on every code modification.
