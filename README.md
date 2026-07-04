# EduHub — AI-Powered Educational Platform Backend

> **Graduation Project** — a production-grade AI backend microservice designed to operate as part of a larger educational portal ecosystem.

EduHub is the backend engine of an AI-powered university portal. It provides an intelligent tutoring chatbot, automated lecture ingestion, batch essay grading, and dynamic summarization — all as isolated, asynchronous services built in FastAPI and Python.

---

## At a Glance: Key AI Techniques

| Technique | Where Used |
|---|---|
| **Cyclic Agentic RAG — DAG planning over `bind_tools`** | Chatbot — single LLM call produces a full parallel execution plan instead of one tool at a time |
| **Parallel async tool execution** (`asyncio.gather`) | RAG Executor — independent retrieval steps run concurrently, eliminating sequential LLM bottleneck |
| **Cyclic LangGraph with self-correction** | Chatbot — Planner → Executor → Reflection loop with replan on failure |
| **Hybrid Search** (dense embeddings + BM25 sparse) | Vector retrieval — combines semantic similarity with exact keyword matching |
| **Reciprocal Rank Fusion (RRF)** | Merges multi-query and multi-source retrieval result lists |
| **Cohere Cross-Encoder Reranking** | Final relevance re-scoring of candidate chunks against the original query |
| **LLM Multi-Query Expansion** | Generates 2–4 search variations before hitting the vector database |
| **Embedding-based Fuzzy Name Resolution** | Resolves natural language lecture/course names to exact DB primary keys via cosine similarity |
| **Adaptive Student Persona** | Persisted per-student profile updated asynchronously each session |
| **Rolling Session Summary** | Incremental LLM-powered summary compressed and stored per session |
| **Cross-turn RAG Memory** | Last 3 turns of tool outputs injected as context into new retrievals |
| **OCR + Structure-Aware PDF Parsing** | Azure AI Document Intelligence preserves section headers, tables, and paragraphs — no naive character splits |
| **Fire-and-forget Evaluation Pipeline** | Per-response structured LLM telemetry pushed to MongoDB asynchronously |
| **LangSmith Tracing** | Full graph and chain tracing for debugging and quality monitoring |

---

## Project Context

This repository is a **graduation project** implementing the AI backend microservice of a larger **educational portal platform**. In the full system architecture, this service exposes REST endpoints consumed by a frontend portal that aggregates multiple learning management features. The service is independently deployable and designed for horizontal scalability.

---

## Chatbot Service — Agentic AI Tutor

> The primary and most technically complex component of this project.

**Entry:** `src/services/chatbot/chatbot_service.py`  
**Detailed docs:** [`CHATBOT_README.md`](src/services/chatbot/CHATBOT_README.md) · [`RAG_README.md`](src/services/chatbot/agents/rag/RAG_README.md)

A stateful AI tutoring assistant named **Luma**, implemented as a two-level LangGraph system. The key architectural decision throughout is **replacing the standard `bind_tools` agent loop with a custom Cyclic DAG planning architecture** — a deliberate trade-off to eliminate sequential LLM bottlenecks and reduce token consumption.

### Why Cyclic DAG Over `bind_tools`?

The default LangChain/LangGraph agent pattern (`bind_tools`) works as a loop: the LLM picks **one tool at a time**, observes the result, and decides the next tool. For a tutoring system where a single question might need to resolve a lecture name, then fetch that lecture's content, and simultaneously search session history, this means **N tools = N sequential LLM calls** — with every intermediate result going back through the LLM just to decide the next step.

This system replaces that pattern entirely:

| | `bind_tools` Loop | Cyclic DAG (this system) |
|---|---|---|
| **LLM calls for tool selection** | 1 per tool (N calls for N tools) | **1 total** — Planner emits the full plan upfront |
| **Tool execution** | Sequential, one at a time | **Parallel** — independent steps run via `asyncio.gather` |
| **Token cost** | All intermediate results re-injected per call | Tool results stay in the executor's state, not re-tokenized |
| **Failure recovery** | No built-in retry logic | Reflection node triggers targeted replan with failure context |
| **Dependency handling** | Implicit (LLM decides order) | Explicit `depends_on` DAG — deterministic, traceable |

**Concretely:** A query that needs 3 independent tool calls costs **1 Planner LLM call + 3 parallel async tool calls** (no LLM involved in execution) instead of **3 sequential LLM calls + 3 sequential tool calls**.

### Two-Level Graph Structure

**Outer Graph (3 nodes):**

```
[Orchestrator] ── route_to_rag ──► [RAG Node] ──► [Answering — Luma]
      └──────── direct_answer ────────────────────► [Answering — Luma]
```

- **OrchestratorNode** (`temp=0.0`): Routes each query, rewrites it to a standalone form (resolves pronouns), and flags whether the persona/summary needs background updating.
- **RAG Node**: Wraps the RAG subgraph. Injects deduplicated tool outputs from the last 3 turns for cross-turn memory continuity.
- **AnsweringNode — Luma** (`temp=0.7`): Socratic AI mentor. Grounded in retrieved context, cites sources inline, adapts to student language and knowledge level, enforces scope guardrails, and captures full LLM token telemetry per response.

**Inner Graph — Agentic RAG Subgraph (4 nodes, cyclic):**

```
Planner → Executor → Reflection → (replan → Planner | success/clarification → Finalize)
```

- **PlannerNode** (`temp=0.1`): Single LLM call that converts the user query into a typed `PlanStep` DAG. Each step carries `tool_name`, `args`, and `depends_on` references like `$step_1.lectures[0].id` resolved at runtime. Enforces course-scope guardrails from the enrolled courses list.
- **ExecutorNode** (no LLM): Topologically walks the DAG. Resolves `$`-prefixed variable references via path traversal against live step outputs. Runs all dependency-satisfied steps in **parallel** via `asyncio.gather`. Breaks early on first failure and surfaces it to Reflection.
- **ReflectionNode** (`temp=0.0`): Classifies whether retrieved outputs are sufficient (`success`), need a different strategy (`replan`), or the query is ambiguous (`clarification`). Hard cap at 3 planning attempts.
- **FinalizeNode** (no LLM): Aggregates and deduplicates all tool outputs across all attempts into a single `RAGSubgraphOutput`.

### Advanced Vector Retrieval Pipeline

Every VDB tool call passes through a multi-stage pipeline before returning results:

1. **LLM Multi-Query Expansion** → 2–4 semantically distinct reformulations
2. **Hybrid Search** → dense (OpenAI embeddings) + sparse (BM25) run concurrently in Qdrant
3. **Intra-query RRF** → merges dense + sparse per query (0.7 dense / 0.3 sparse weight)
4. **Cross-query RRF** → merges all per-variation results into one candidate pool
5. **Cohere Cross-Encoder Reranking** (`rerank-english-v3.0`) → joint (query, document) relevance scoring
6. **Threshold filtering** → per-tool relevance cutoffs discard low-confidence chunks

### Session Memory Architecture

| Store | What's Persisted | Lifetime |
|---|---|---|
| Redis | Messages, persona, summary, student_courses, per-turn tool outputs | Session duration |
| MongoDB | Student persona documents, per-response evaluation records (LLM telemetry) | Permanent |
| Qdrant | Session summary embeddings (semantic cross-session retrieval) | Permanent |
| SQL Server | Student enrollments, course metadata, lecture listings | Source of truth |

---

## Other Services

### Lecture Storage Pipeline — Async ETL

**Entry:** `src/orchestrators/lecture_orchestrator.py`

An asynchronous ETL orchestrator that transforms raw PDF lecture files into fully searchable knowledge bases:

1. **OCR + Structure-Aware PDF Parsing** — Azure AI Document Intelligence extracts content with full structural awareness: section headings, paragraph boundaries, table cells, and page markers are preserved as discrete elements. This is a critical quality advantage — naive character-count splitting destroys semantic coherence, while structure-aware chunking ensures every retrieved passage carries complete context.
2. **Semantic Chunking** — Chunks are constructed to respect document structure boundaries, not arbitrary character counts.
3. **Embedding** — Chunks are vectorized using the configured OpenAI embedding model.
4. **Hybrid Indexing** — Stored in Qdrant with both dense vectors and BM25 sparse vectors for hybrid retrieval.
5. **Metadata Cataloguing** — Lecture metadata (course ID, lecture ID, title, page numbers) stored in MongoDB and SQL Server for structured lookups.
6. **Summarization** — Multi-level summaries generated per lecture and stored in MongoDB.

### Grading Service — Batch AI Essay Evaluator

**Entry:** `src/services/grading/`

Automates university essay grading at scale. Runs concurrent LangChain evaluation chains (`function_calling` → structured `GradingOutput`) with a carefully engineered prompt that enforces realistic human-like score distribution — explicitly preventing score clustering toward the middle via a mandatory step-by-step concept coverage analysis before scoring.

### Summarization Service — Multi-Level LLM Summarizer

**Entry:** `src/services/summarize/summarize_service.py`

Generates structured, multi-level summaries of parsed lecture content. Stored in MongoDB and accessible to students via the RAG retrieval layer.

---

## Technical Architecture

### Modular Layered Design

```
src/
├── routers/          # FastAPI route handlers (input validation, DI wiring)
├── services/         # Pure business logic (chatbot, grading, lectures, summarize, chunking, embedding)
├── orchestrators/    # Multi-service coordination (LectureOrchestrator)
├── repositories/     # Database query abstractions (LectureRepo, EvaluationRepo, StudentPersonaRepo)
├── integrations/     # Generic interfaces for external systems (Qdrant, Redis, OpenAI, Azure)
├── schemas/          # Pydantic request/response models
├── dtos/             # Internal data transfer objects
├── models/           # Persistent data models (EvaluationModel)
├── helpers/          # Logging, utilities
└── core/             # Settings, dependency injection
```

Each layer has a single responsibility. `integrations/` wraps all SDK calls behind interfaces so services remain testable without live infrastructure.

### Asynchronous-First Design

Every I/O operation is `async`/`await`. Background tasks (`asyncio.create_task`) handle non-blocking work (evaluation persistence, persona/summary updates). Concurrent workloads (multi-query retrieval, parallel tool execution) use `asyncio.gather`.

### Repository Structure

```
eduhub/
├── src/
│   ├── main.py                    # FastAPI app factory
│   ├── services/
│   │   ├── chatbot/               # Two-level LangGraph chatbot + Agentic RAG
│   │   │   ├── agents/rag/        # RAG subgraph (Planner, Executor, Reflection, Finalize)
│   │   │   ├── nodes/             # Outer graph nodes (Orchestrator, RAG, Answering)
│   │   │   ├── chains/            # Summary and persona LangChain chains
│   │   │   └── CHATBOT_README.md
│   │   ├── grading/               # Batch AI essay grading engine
│   │   ├── lectures/              # Lecture CRUD and content management
│   │   ├── chunking/              # Structure-aware text chunking
│   │   ├── summarize/             # Multi-level LLM summarization
│   │   ├── embedding/             # Vector embedding pipeline
│   │   └── vdb_service/           # Qdrant collection management
│   ├── orchestrators/             # LectureOrchestrator (ETL pipeline coordination)
│   ├── integrations/              # Qdrant, Redis, OpenAI, Azure wrappers
│   └── repositories/              # MongoDB/SQL query abstractions
├── docker/                        # Docker Compose + environment configs
├── .github/workflows/             # GitHub Actions CI pipeline
├── tests/                         # Test suite
├── requirements.txt
└── langgraph.json                 # LangGraph Studio configuration
```
