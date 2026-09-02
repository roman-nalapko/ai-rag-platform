# AI RAG Platform Backlog

This file is the single navigation point for future work. Keep it practical:
small tasks, clear priority, explicit acceptance criteria, and no vague
"improve everything" items.

## How to use this backlog

### Statuses

| Status | Meaning |
| --- | --- |
| `Backlog` | Valid idea, not scheduled yet |
| `Ready` | Clear scope and acceptance criteria |
| `In Progress` | Currently being implemented |
| `Review` | Code is done, needs checks or cleanup |
| `Done` | Implemented, tested, documented |
| `Blocked` | Waiting for a decision, dependency, or external setup |

### Priorities

| Priority | Meaning |
| --- | --- |
| `P0` | Broken core flow, security issue, or setup blocker |
| `P1` | Strong portfolio / production-readiness improvement |
| `P2` | Useful enhancement, not urgent |
| `P3` | Nice-to-have or future exploration |

### Task format

Use this format for every new backlog item:

```text
### [P1] Short task title

Status: Ready
Area: ingestion | retrieval | qa | api | db | infra | docs | tests

Problem:
- What is missing or painful?

Scope:
- What exactly should be changed?

Acceptance criteria:
- [ ] Clear observable result
- [ ] Tests/docs updated if relevant

Out of scope:
- What should not be added in this task?
```

## Current focus

The project is already a strong local-first RAG MVP. The next work should make
it easier to verify, more reliable in production-like scenarios, and clearer
for recruiters/interviewers.

Recommended sequence:

1. Improve demo and local developer workflow.
2. Add integration tests for PostgreSQL and Qdrant flows.
3. Improve retrieval quality and evaluation.
4. Add authentication and real tenant isolation.
5. Replace in-process background jobs with a durable queue.

## P0 - Fix immediately

No known P0 items.

## P1 - Next production polish

### [P1] Add Makefile for common workflows

Status: Done
Area: infra

Problem:

- Setup and demo commands are spread across README and docs.
- Recruiters and reviewers should be able to run the project without hunting
  for commands.

Scope:

- Add a `Makefile` with commands for setup, migrations, tests, lint, Docker
  startup, Docker shutdown, and demo helper commands.

Acceptance criteria:

- [x] `make test` runs pytest.
- [x] `make lint` runs Ruff.
- [x] `make migrate` runs Alembic upgrade.
- [x] `make docker-up` starts core services.
- [x] README references the Makefile.

Out of scope:

- Do not change application behavior.

### [P1] Add deterministic demo seed script

Status: Done
Area: docs / api

Problem:

- The demo flow is documented, but the user still needs to manually copy IDs
  between commands.

Scope:

- Add a local script that creates a user, creates a knowledge base, uploads the
  sample document, polls indexing status, runs search, and runs QA.

Acceptance criteria:

- [x] Script works against local API.
- [x] Script prints created IDs and final QA result.
- [x] Docs explain how to run it.

Out of scope:

- Do not add frontend.
- Do not require paid APIs.

### [P1] Add PostgreSQL + Qdrant integration tests

Status: Done
Area: tests

Problem:

- Current tests avoid external dependencies, which is good for unit-level CI,
  but the most important RAG flows need integration proof.

Scope:

- Add a separate integration test suite that can run with Docker Compose.
- Test migrations, document metadata persistence, chunk persistence, Qdrant
  collection creation, and vector payload filtering.

Acceptance criteria:

- [x] Integration tests are clearly separated from fast unit tests.
- [x] Tests can be run locally with one documented command.
- [x] CI keeps fast tests by default unless integration services are available.

Out of scope:

- Do not require LM Studio in CI.

### [P1] Add document delete and re-index flow

Status: Done
Area: ingestion / rag

Problem:

- Documents can be uploaded and indexed, but not deleted or re-indexed.
- This makes the lifecycle incomplete for a SaaS-style backend.

Scope:

- Add document deletion that removes PostgreSQL rows and Qdrant vectors.
- Add retry/re-index for failed or stale documents.

Acceptance criteria:

- [x] Deleting a document removes chunks and vectors.
- [x] Re-indexing updates chunks and vectors safely.
- [x] Failure cases are visible through document status.

Out of scope:

- Do not add user-facing frontend.

### [P1] Add document and conversation listing endpoints

Status: Done
Area: api / services

Problem:

- Users could upload documents and start conversations, but had no way to list
  existing documents or conversations in a knowledge base.

Scope:

- Add `GET /documents?knowledge_base_id=...&limit=50&offset=0` with chunk counts.
- Add `GET /conversations?knowledge_base_id=...&limit=50&offset=0`.
- Enforce tenant isolation so users can only list resources in their own knowledge bases.

Acceptance criteria:

- [x] Document listing returns paginated documents with chunk counts.
- [x] Conversation listing returns paginated conversation sessions.
- [x] Tenant boundaries are verified and covered by tests.

Out of scope:

- Do not change existing single-resource routes.

### [P1] Add knowledge base retrieval and cascading deletion

Status: Done
Area: api / services / rag

Problem:

- Knowledge bases could be created and listed, but not inspected individually or deleted
  with cascading vector and file cleanup.

Scope:

- Add `GET /knowledge-bases/{id}`.
- Add `DELETE /knowledge-bases/{id}` with cascading PostgreSQL, storage file, and Qdrant points cleanup.

Acceptance criteria:

- [x] `GET /knowledge-bases/{id}` returns knowledge base details.
- [x] `DELETE /knowledge-bases/{id}` removes DB records, files, and Qdrant vectors.
- [x] Cross-tenant access is denied with 404.

Out of scope:

- Do not add organization-level ownership yet.

### [P1] Add zero-config test setup for fresh clones

Status: Done
Area: tests / dx

Problem:

- Running `pytest` immediately after cloning failed with Pydantic settings validation
  unless `.env` was manually created.

Scope:

- Set test fallback environment variables in `tests/conftest.py` before application imports.

Acceptance criteria:

- [x] `pytest` passes out of the box on a fresh clone with no `.env` file.

Out of scope:

- Do not change production settings loading.

### [P2] Add Unicode tokenization and batch embedding optimization

Status: Done
Area: rag / llm

Problem:

- `KeywordOverlapReranker` tokenized ASCII only, dropping Cyrillic/multilingual tokens.
- Document ingestion embedded chunks one-by-one rather than in batch.

Scope:

- Upgrade reranker token pattern to `\w+` with Unicode flag.
- Add `embed_texts` batch embedding method to `LMStudioClient` and use in `VectorStoreService`.

Acceptance criteria:

- [x] Multilingual / Unicode keyword overlap reranking works and is tested.
- [x] Chunks are embedded efficiently via batched API requests.

Out of scope:

- Do not require external neural reranker models.

## P1 - RAG quality

### [P1] Add structured SSE events with sources citation

Status: Done
Area: api / qa / frontend

Problem:
- Plain text SSE streams required clients to wait or guess which source chunks were used.

Scope:
- Emit typed SSE events (`event: sources`, `event: token`, `event: done`, and `data: [DONE]`).
- Upgrade frontend web demo to render source chunk cards immediately during streaming.

Acceptance criteria:
- [x] Stream emits `event: sources` with document chunk payloads before tokens start.
- [x] Web demo parses typed SSE events and updates UI real-time.
- [x] Tests cover typed event emission and error status mappings.

### [P1] Add Prometheus metrics exporter

Status: Done
Area: observability / infra

Problem:
- Production systems need metric counters and latency histograms for Prometheus / Grafana scraping.

Scope:
- Implement zero-dependency Prometheus metrics registry emitting standard exposition format.
- Add `GET /metrics` endpoint.
- Instrument HTTP request durations, vector search latency, and worker jobs.

Acceptance criteria:
- [x] `GET /metrics` exports counters and histograms with label dimensions.
- [x] All HTTP requests and durations are automatically measured.
- [x] Unit and API tests verify metric rendering.

### [P1] Add CI service containers for automated integration tests

Status: Done
Area: infra / tests / ci

Problem:
- Integration tests existed locally but did not run automatically on GitHub Actions PRs.

Scope:
- Add ephemeral `postgres:17-alpine` and `qdrant/qdrant:latest` service containers to `.github/workflows/ci.yml`.
- Run migrations and `RUN_INTEGRATION_TESTS=1 pytest -v` in CI.

Acceptance criteria:
- [x] GitHub Actions workflow runs full PostgreSQL and Qdrant integration tests.
- [x] Tests verify migrations, multi-tenant persistence, and vector payload filters.

### [P1] Add Hybrid Retrieval with Reciprocal Rank Fusion (RRF)

Status: Done
Area: retrieval / rag

Problem:
- Dense vector similarity can miss exact keyword / identifier matches.

Scope:
- Implement generic Reciprocal Rank Fusion (`reciprocal_rank_fusion`) algorithm.
- Add PostgreSQL full-text search (`search_text`) and hybrid retrieval (`search_hybrid`).

Acceptance criteria:
- [x] RRF formula `sum(1 / (k + rank))` merges ranked lists properly.
- [x] Tests verify generic RRF behavior, rank ordering, and candidate limits.

### [P1] Add Multi-Provider LLM & Embedding Client Factory

Status: Done
Area: llm / architecture

Problem:
- Tightly coupling to LM Studio naming made it harder to use Ollama, OpenAI, vLLM, or other OpenAI-compatible engines.

Scope:
- Define `LLMClient` protocol and `get_llm_client` / `OpenAICompatibleClient` abstractions.
- Support interchangeable OpenAI-compatible endpoints with backwards compatibility.

Acceptance criteria:
- [x] Clean `LLMClient` protocol and `get_llm_client` factory.
- [x] Backwards-compatible aliases preserved.

### [P1] Improve retrieval evaluation beyond keyword matching

Status: Done
Area: evaluation

Problem:

- Keyword matching is transparent and simple, but it does not measure retrieval
  quality, source relevance, or groundedness deeply.

Scope:

- Add retrieval-oriented metrics such as source hit rate, top-k recall on known
  documents, and answer source coverage.

Acceptance criteria:

- [x] Evaluation report separates answer keyword accuracy from retrieval
  quality.
- [x] Docs explain how to add expected source chunks or documents.

Out of scope:

- Do not use paid judge models.

### [P2] Add optional reranking layer

Status: Done  
Area: retrieval

Problem:

- Pure vector similarity can return chunks that are semantically close but not
  the best final context.

Scope:

- Add an optional reranker abstraction.
- Keep default mode local-first and disabled unless configured.
- Over-fetch Qdrant candidates only when reranking is enabled.

Acceptance criteria:

- [x] Search and QA can run with or without reranking.
- [x] Configuration is documented.
- [x] Existing behavior remains unchanged by default.

Out of scope:

- Do not introduce paid APIs as a requirement.

### [P2] Add embedding model metadata to indexed vectors

Status: Done  
Area: rag / db

Problem:

- Vectors currently depend on the active embedding model, but model identity is
  not tracked as first-class metadata.

Scope:

- Store embedding model name/version in indexed vector payload metadata.
- Document how to inspect payloads and when manual re-indexing is required
  after model changes.

Acceptance criteria:

- [x] Indexed payload includes embedding model metadata.
- [x] Docs explain when re-indexing is required.

Out of scope:

- Do not implement automatic migration of existing vectors yet.

## P1 - SaaS and security foundation

### [P1] Add JWT authentication

Status: Done  
Area: api / security

Problem:

- The current system has SaaS data models but no real authentication.

Scope:

- Add local demo JWT token issuance for existing users.
- Scope user actions through authenticated identity instead of trusting explicit
  user IDs alone.

Acceptance criteria:

- [x] Protected endpoints require a valid token.
- [x] Users can only access their own knowledge bases.
- [x] Tests cover authorization boundaries.

Out of scope:

- Do not add OAuth providers yet.

### [P1] Add tenant isolation checks across all data access

Status: Done  
Area: services / db

Problem:

- Knowledge-base scoping exists for search and QA, but full authorization
  boundaries should be enforced consistently once auth is added.

Scope:

- Review every read/write path for tenant isolation.
- Enforce owner checks for knowledge bases, documents, conversations, Search,
  and QA.
- Add tests for authorization boundaries.

Acceptance criteria:

- [x] Cross-tenant document access is denied.
- [x] Cross-tenant conversation access is denied.
- [x] Cross-tenant search/QA remains filtered.

Out of scope:

- Do not add billing or organizations in this task.

## P1 - Background processing

### [P1] Replace FastAPI BackgroundTasks with durable queue

Status: Done  
Area: ingestion / infra

Problem:

- In-process background tasks are simple but not durable across restarts.

Scope:

- Introduce a lightweight PostgreSQL-backed document job queue.
- Move extraction, chunking, embedding, and Qdrant indexing into a worker.
- Run a separate Docker Compose worker service for container demos.

Acceptance criteria:

- [x] Upload returns quickly with `pending`.
- [x] Worker processes jobs independently.
- [x] Failed jobs persist error state.
- [x] Docker Compose starts worker dependencies.

Out of scope:

- Do not add Kubernetes.

### [P2] Add upload limits and safer file validation

Status: Done
Area: ingestion / security

Problem:

- Upload handling should define clear size and content constraints before any
  public deployment.

Scope:

- Add configurable max upload size.
- Validate extension and MIME type consistently.
- Improve failure messages.

Acceptance criteria:

- [x] Oversized files fail with a clear HTTP error.
- [x] Unsupported content types fail before background indexing.
- [x] Docs mention limits.

Out of scope:

- Do not add virus scanning yet.

## P2 - API and developer experience

### [P2] Add pagination for list endpoints

Status: Done
Area: api

Problem:

- List endpoints will not scale well if they return all records.

Scope:

- Add `limit` and `offset` or cursor pagination where relevant.

Acceptance criteria:

- [x] Knowledge-base lists are paginated.
- [x] Future document/conversation lists use the same pattern.

Out of scope:

- Do not change existing response models without compatibility notes.

### [P2] Add readiness endpoint

Status: Done
Area: api / infra

Problem:

- `/health` proves the API process is running, but deployment environments also
  need dependency readiness.

Scope:

- Add `/health/ready` to check PostgreSQL and Qdrant connectivity.

Acceptance criteria:

- [x] Returns healthy only when required dependencies are reachable.
- [x] Does not call LM Studio unless explicitly requested.

Out of scope:

- Do not replace `/health`.

### [P2] Add API collection for demos

Status: Done
Area: docs / dx

Problem:

- Curl examples are good, but API collections make demos faster.

Scope:

- Add Bruno or Postman collection with health, create user, create knowledge
  base, upload, poll, search, QA, and stream examples.

Acceptance criteria:

- [x] Collection is committed without secrets.
- [x] Docs explain import and environment variables.

Out of scope:

- Do not require proprietary tooling.

## P3 - Future platform capabilities

### [P3] Add minimal web demo UI

Status: Done  
Area: frontend / demo

Problem:

- A small UI would make the project easier to demo to non-technical reviewers.

Scope:

- Add a minimal static chat/upload UI mounted at `/demo`.
- Keep UI assets under `app/web` and consume existing API endpoints only.

Acceptance criteria:

- [x] Upload, indexing status, search, QA, and streaming chat are visible.
- [x] UI remains separate from backend logic.

Out of scope:

- Do not redesign backend APIs for the UI.

### [P3] Add deployment profile

Status: Done  
Area: infra

Problem:

- The project is local-first. A production deployment story would be useful
  later, but should not distract from core backend quality now.

Scope:

- Document a small-cloud deployment path with managed PostgreSQL, Qdrant, and
  external/local-compatible LLM provider.
- Include API/worker separation and durable job queue implications.

Acceptance criteria:

- [x] Deployment doc includes required environment variables.
- [x] Security and cost limitations are explicit.

Out of scope:

- Do not deploy automatically from CI.

## Parking lot

Ideas to revisit later:

- Hybrid BM25 + vector search.
- Per-document access permissions.
- Organization/team model.
- Admin dashboard.
- Model comparison reports.
- Advanced prompt versioning.
- Citation highlighting by text span.

## Completed baseline

- FastAPI async API.
- PostgreSQL 17 with async SQLAlchemy.
- Alembic migrations.
- Qdrant vector search.
- LM Studio local LLM provider.
- PDF/TXT ingestion.
- Background indexing status.
- Multi-tenant knowledge bases.
- Knowledge-base-scoped search and QA.
- Conversation memory.
- Streaming QA endpoint.
- Structured JSON logging.
- Offline RAG evaluation.
- Docker setup.
- GitHub Actions CI.
