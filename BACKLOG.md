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

Status: Review
Area: docs / api

Problem:

- The demo flow is documented, but the user still needs to manually copy IDs
  between commands.

Scope:

- Add a local script that creates a user, creates a knowledge base, uploads the
  sample document, polls indexing status, runs search, and runs QA.

Acceptance criteria:

- [ ] Script works against local API.
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

## P1 - RAG quality

### [P1] Improve retrieval evaluation beyond keyword matching

Status: Backlog  
Area: evaluation

Problem:

- Keyword matching is transparent and simple, but it does not measure retrieval
  quality, source relevance, or groundedness deeply.

Scope:

- Add retrieval-oriented metrics such as source hit rate, top-k recall on known
  documents, and answer source coverage.

Acceptance criteria:

- [ ] Evaluation report separates answer keyword accuracy from retrieval
  quality.
- [ ] Docs explain how to add expected source chunks or documents.

Out of scope:

- Do not use paid judge models.

### [P2] Add optional reranking layer

Status: Backlog  
Area: retrieval

Problem:

- Pure vector similarity can return chunks that are semantically close but not
  the best final context.

Scope:

- Add an optional reranker abstraction.
- Keep default mode local-first and disabled unless configured.

Acceptance criteria:

- [ ] Search and QA can run with or without reranking.
- [ ] Configuration is documented.
- [ ] Existing behavior remains unchanged by default.

Out of scope:

- Do not introduce paid APIs as a requirement.

### [P2] Add embedding model metadata to indexed vectors

Status: Backlog  
Area: rag / db

Problem:

- Vectors currently depend on the active embedding model, but model identity is
  not tracked as first-class metadata.

Scope:

- Store embedding model name/version in document or chunk metadata.
- Add a way to detect stale vectors after model changes.

Acceptance criteria:

- [ ] Indexed payload includes embedding model metadata.
- [ ] Docs explain when re-indexing is required.

Out of scope:

- Do not implement automatic migration of existing vectors yet.

## P1 - SaaS and security foundation

### [P1] Add JWT authentication

Status: Backlog  
Area: api / security

Problem:

- The current system has SaaS data models but no real authentication.

Scope:

- Add registration/login or local demo auth.
- Scope user actions through authenticated identity instead of explicit user IDs.

Acceptance criteria:

- [ ] Protected endpoints require a valid token.
- [ ] Users can only access their own knowledge bases.
- [ ] Tests cover authorization boundaries.

Out of scope:

- Do not add OAuth providers yet.

### [P1] Add tenant isolation checks across all data access

Status: Backlog  
Area: services / db

Problem:

- Knowledge-base scoping exists for search and QA, but full authorization
  boundaries should be enforced consistently once auth is added.

Scope:

- Review every read/write path for tenant isolation.
- Add tests for cross-tenant access denial.

Acceptance criteria:

- [ ] Cross-tenant document access is denied.
- [ ] Cross-tenant conversation access is denied.
- [ ] Cross-tenant search/QA remains filtered.

Out of scope:

- Do not add billing or organizations in this task.

## P1 - Background processing

### [P1] Replace FastAPI BackgroundTasks with durable queue

Status: Backlog  
Area: ingestion / infra

Problem:

- In-process background tasks are simple but not durable across restarts.

Scope:

- Introduce Redis + Celery or another lightweight worker.
- Move extraction, chunking, embedding, and Qdrant indexing into a worker.

Acceptance criteria:

- [ ] Upload returns quickly with `pending`.
- [ ] Worker processes jobs independently.
- [ ] Failed jobs persist error state.
- [ ] Docker Compose starts worker dependencies.

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

Status: Backlog  
Area: frontend / demo

Problem:

- A small UI would make the project easier to demo to non-technical reviewers.

Scope:

- Add a minimal chat/upload UI that consumes the existing API.

Acceptance criteria:

- [ ] Upload, indexing status, search, QA, and streaming chat are visible.
- [ ] UI remains separate from backend logic.

Out of scope:

- Do not redesign backend APIs for the UI.

### [P3] Add deployment profile

Status: Backlog  
Area: infra

Problem:

- The project is local-first. A production deployment story would be useful
  later, but should not distract from core backend quality now.

Scope:

- Document a small-cloud deployment path with managed PostgreSQL, Qdrant, and
  external/local-compatible LLM provider.

Acceptance criteria:

- [ ] Deployment doc includes required environment variables.
- [ ] Security and cost limitations are explicit.

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
