# AI RAG Platform

[![CI](https://github.com/roman-nalapko/ai-rag-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/roman-nalapko/ai-rag-platform/actions/workflows/ci.yml)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.125+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-336791.svg)](https://www.postgresql.org)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-dc2626.svg)](https://qdrant.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Local-first RAG platform for building private AI assistants over documents.**

**Built with:** FastAPI · PostgreSQL · Qdrant · LM Studio · Docker

> [!IMPORTANT]
> This repository is a local-first engineering project, not a turnkey public
> SaaS. The built-in user creation and token issuance flows are intentionally
> demo-only and do not prove user identity. Keep the service on a trusted local
> network, or set `DEMO_MODE_ENABLED=false` and add production authentication
> before exposing it publicly. See [Deployment](docs/DEPLOYMENT.md).

## Features

- Async document ingestion pipeline with batch embeddings
- Hybrid retrieval (Qdrant Dense Vectors + PostgreSQL Full-Text Search) with Reciprocal Rank Fusion (RRF)
- Unicode-aware multilingual reranker
- Multi-tenant knowledge bases and scoped tenant isolation
- Multi-turn conversation memory
- Structured SSE streaming with real-time source citations
- Built-in Prometheus metrics exporter (`/metrics`)
- Offline RAG quality evaluation
- CI/CD pipeline with live PostgreSQL 17 and Qdrant service containers

## Architecture preview

```text
Document
   ↓
Chunking
   ↓
Embeddings (Batch)
   ↓
Hybrid Retrieval (Qdrant Vectors + PostgreSQL FTS via RRF)
   ↓
Context + Prompt
   ↓
Multi-Provider LLM
   ↓
Streaming Answer + Citations
```

## Why this project exists

This project demonstrates production AI engineering patterns: clean
architecture, async processing, vector databases, LLM abstraction, evaluation
and deployment workflows.

**Project links:** [guided demo](docs/DEMO_FLOW.md) ·
[architecture](docs/ARCHITECTURE.md) · [interview topics](docs/INTERVIEW.md) ·
[resume bullets](docs/RESUME.md) · [API examples](docs/API_EXAMPLES.md) ·
[API collection](docs/api-collection/README.md) ·
[deployment](docs/DEPLOYMENT.md) · [changelog](CHANGELOG.md) ·
[contributing](CONTRIBUTING.md) · [security](SECURITY.md) · [backlog](BACKLOG.md)

## Quick start

Prerequisites: Docker Desktop and LM Studio with one chat model and one
embedding model. Enable LM Studio's Local Server on port `1234` and local
network access, then:

```bash
cp .env.example .env
# Set the exact LM_STUDIO_CHAT_MODEL and LM_STUDIO_EMBEDDING_MODEL IDs in .env
# Replace JWT_SECRET_KEY with a random value of at least 32 characters.

docker compose up -d postgres qdrant
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d api

curl http://localhost:8000/health
```

Open [Swagger UI](http://localhost:8000/docs), then follow the
[eight-step demo](docs/DEMO_FLOW.md) using `examples/sample_document.txt`.

## Common commands

The repository includes a small `Makefile` for the most common local workflows:

```bash
make help
make docker-up
make migrate
make run
make lint
make test
make demo
```

For Docker-only API startup:

```bash
make docker-api-up
make migrate-docker
```

## Architecture

```text
                         OpenAI-compatible API
                    +----------------------------+
                    |         LM Studio          |
                    | embeddings + chat model    |
                    +-------------^--------------+
                                  |
+---------+      +----------------+-----------------+
| Client  | ---> | FastAPI: api/ HTTP layer         |
+---------+      +----------------+-----------------+
                                  |
                    +-------------v--------------+
                    | services/ business flows   |
                    | ingest | search | chat      |
                    +------+------+--------------+
                           |      |
              +------------+      +-------------+
              |                                 |
    +---------v----------+            +---------v----------+
    | PostgreSQL 17      |            | Qdrant             |
    | tenants + jobs     |            | vectors + payload  |
    +--------------------+            +--------------------+
              ^
              |
    +---------+----------+
    | worker service     |
    | document indexing  |
    +--------------------+
```

The HTTP layer validates requests and maps errors. Services orchestrate use
cases. Provider-specific LM Studio and Qdrant operations remain isolated in
`llm/` and `rag/`. See [Architecture](docs/ARCHITECTURE.md) for the detailed
module and data-flow description.

## Tech stack

| Area                | Technology                                                   |
| ------------------- | ------------------------------------------------------------ |
| Language            | Python 3.14                                                  |
| API                 | FastAPI, Pydantic v2, Uvicorn                                |
| Database            | PostgreSQL 17, SQLAlchemy async, asyncpg                     |
| Vector store        | Qdrant, async Qdrant client, cosine distance                 |
| Local AI            | LM Studio, OpenAI-compatible API, official OpenAI Python SDK |
| Document processing | pypdf, UTF-8 text extraction                                 |
| Infrastructure      | Docker Compose                                               |

## Key features

- **RAG ingestion:** PDF/TXT extraction, overlapping chunks, durable
  PostgreSQL-backed jobs, local embeddings, dynamic Qdrant collections,
  embedding model metadata, and observable processing states.
- **Upload safety:** configurable raw document size limits plus matching PDF/TXT
  filename-extension and declared-content-type validation before indexing.
- **Scoped retrieval:** top-K cosine search with mandatory knowledge-base
  payload filters, optional local reranking, scores, and complete source
  metadata.
- **Grounded chat:** strict context-only prompting, deterministic fallback,
  source attribution, persistent conversation history, and SSE streaming.
- **SaaS foundation:** users, knowledge bases, documents, jobs, chunks,
  conversations, and messages modelled in PostgreSQL with cascade rules.
- **Failure handling:** explicit provider errors, failed-document diagnostics,
  transactional chunk writes, and compensating Qdrant deletion.
- **Quality engineering:** offline RAG evaluation with answer and source
  metrics, pytest API contracts, Ruff, GitHub Actions, and a reproducible
  sample document/demo.
- **Observability:** JSON logs, `X-Request-ID`, and embedding, retrieval,
  generation, and indexing latency events without logging model inputs.
- **Local deployment:** LM Studio inference with no paid key, versioned Alembic
  migrations, non-root Python 3.14 Docker images, and separate API/worker
  containers.

## API

| Method | Endpoint                       | Purpose                                         |
| ------ | ------------------------------ | ----------------------------------------------- |
| `GET`  | `/health`                      | API process health                              |
| `GET`  | `/health/ready`                | PostgreSQL and Qdrant readiness                 |
| `GET`  | `/health/llm`                  | LM Studio embedding health and dimensions       |
| `GET`  | `/metrics`                     | Prometheus metrics exporter                     |
| `POST` | `/users`                       | Create a user account record                    |
| `POST` | `/auth/demo-token`             | Issue a local demo JWT for an existing user     |
| `POST` | `/knowledge-bases`             | Create a user-owned knowledge base              |
| `GET`  | `/knowledge-bases?user_id=...&limit=50&offset=0` | List one user's knowledge bases |
| `GET`  | `/knowledge-bases/{id}`        | Get knowledge base details                      |
| `DELETE` | `/knowledge-bases/{id}`      | Delete knowledge base, documents, and vectors   |
| `POST` | `/conversations`               | Start a conversation in a knowledge base        |
| `GET`  | `/conversations?knowledge_base_id=...&limit=50&offset=0` | List conversations in a knowledge base |
| `GET`  | `/conversations/{id}/messages` | Read a conversation's chat history              |
| `POST` | `/documents/upload`            | Store a PDF/TXT file and enqueue indexing       |
| `GET`  | `/documents?knowledge_base_id=...&limit=50&offset=0` | List documents in a knowledge base |
| `GET`  | `/documents/{id}`              | Read processing status, chunk count, and errors |
| `POST` | `/documents/{id}/reindex`      | Clear chunks/vectors and enqueue re-indexing    |
| `DELETE` | `/documents/{id}`            | Delete metadata, chunks, vectors, and raw file  |
| `POST` | `/search`                      | Semantic search within one knowledge base       |
| `POST` | `/qa/ask`                      | Knowledge-base-scoped RAG answer with sources   |
| `POST` | `/qa/ask/stream`               | Stream a grounded answer over SSE               |

Interactive documentation is available at
[http://localhost:8000/docs](http://localhost:8000/docs) while the API is
running. Complete curl requests are in [API Examples](docs/API_EXAMPLES.md).
A lightweight browser demo is available at
[http://localhost:8000/demo/](http://localhost:8000/demo/) for user/token
creation, document upload, indexing status, search, normal QA, and streaming
QA. Set `DEMO_MODE_ENABLED=false` before startup to hide the demo UI, account
creation endpoint, and demo-token endpoint.

## Development setup (native API)

### Prerequisites

- Python 3.14
- Docker Desktop with Docker Compose
- [LM Studio](https://lmstudio.ai/download)

### 1. Configure the application

From the repository root:

```bash
cp .env.example .env
python3.14 -m venv venv
source venv/bin/activate
pip install -r requirements.lock
```

### 2. Start PostgreSQL and Qdrant

```bash
docker compose up -d postgres qdrant
docker compose ps
```

PostgreSQL is exposed on `localhost:5432`. Qdrant uses `localhost:6333` for
HTTP and `localhost:6334` for gRPC. The Qdrant dashboard is available at
[http://localhost:6333/dashboard](http://localhost:6333/dashboard).

### 3. Apply database migrations

Application startup never creates or alters database tables. Apply all pending
migrations explicitly:

```bash
alembic upgrade head
```

### 4. Configure LM Studio

1. Install and open LM Studio.
2. Download one small instruct/chat model and one embedding model.
3. On an Apple Silicon machine with 8 GB unified memory, prefer a 2B-4B
   4-bit chat model and keep context between 2048 and 4096 tokens.
4. Open **Developer**, enable the Local Server on port `1234`, and allow model
   loading.
5. Verify the available model IDs:

   ```bash
   curl http://localhost:1234/v1/models
   ```

6. Copy the exact IDs into `.env`:

   ```env
   LM_STUDIO_BASE_URL=http://localhost:1234/v1
   LM_STUDIO_API_KEY=lm-studio
   LM_STUDIO_CHAT_MODEL=distill-e4b-it-4-bit-mlx
   LM_STUDIO_EMBEDDING_MODEL=nomic-ai/text-embedding-nomic-embed-text-v1.5
   LM_STUDIO_TIMEOUT_SECONDS=300
   LM_STUDIO_MAX_TOKENS=64
   RERANKING_ENABLED=false
   RERANKING_CANDIDATE_MULTIPLIER=3
   UPLOAD_STORAGE_PATH=storage/uploads
   UPLOAD_MAX_BYTES=10485760
   ```

   On an 8 GB M1, load the chat model with a 2048-token context and one
   parallel request. The longer API timeout is intentional: memory pressure
   can make even short local completions take more than 30 seconds.

The API key is a local placeholder unless authentication is explicitly enabled
inside LM Studio. Embedding dimensions are discovered dynamically; the current
Nomic configuration returns 768-dimensional vectors.

Optional reranking is disabled by default to preserve vector-search behavior.
Set `RERANKING_ENABLED=true` to over-fetch local Qdrant candidates and reorder
them with the built-in keyword-overlap reranker before Search and QA choose
their final context.

### 5. Start FastAPI

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify the services:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/llm
```

## Detailed Docker setup

The API, PostgreSQL, and Qdrant can run together in Docker Compose. LM Studio
stays on the host so it can use Apple Silicon acceleration and local model
management.

1. Copy the environment template and configure the exact LM Studio model IDs:

   ```bash
   cp .env.example .env
   ```

2. Start LM Studio's Local Server on port `1234`. Enable access from the local
   network so Docker can reach it through `host.docker.internal`.

3. Start data services and build the API image:

   ```bash
   docker compose up -d postgres qdrant
   docker compose build api
   ```

4. Apply migrations as an explicit one-off container task:

   ```bash
   docker compose run --rm api alembic upgrade head
   ```

5. Start and verify the API:

   ```bash
   docker compose up -d api worker
   docker compose ps
   curl http://localhost:8000/health
   ```

Follow structured logs or stop the stack:

```bash
docker compose logs -f api worker
docker compose down
```

Compose uses service DNS names internally:

- PostgreSQL: `postgres:5432`;
- Qdrant: `qdrant:6333`;
- host LM Studio: `host.docker.internal:1234`.

Raw uploads persist in the `uploads_data` named volume. PostgreSQL and Qdrant
use `postgres_data` and `qdrant_data`. The API image never copies `.env`, local
virtual environments, tests, documentation, logs, or local data directories.

## Quick API examples

Create a user, issue a local demo token, and then create a knowledge base:

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email":"engineer@example.com"}'

curl -X POST http://localhost:8000/auth/demo-token \
  -H "Content-Type: application/json" \
  -d '{"user_id":"11111111-1111-1111-1111-111111111111"}'

export TOKEN="paste-access-token-here"

curl -X POST http://localhost:8000/knowledge-bases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"11111111-1111-1111-1111-111111111111",
    "name":"Engineering Docs",
    "description":"Backend and AI documentation"
  }'
```

Upload a document:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "knowledge_base_id=22222222-2222-2222-2222-222222222222" \
  -F "file=@examples/sample_document.txt;type=text/plain"
```

The upload returns HTTP `202` with `status: "pending"`. Poll its status before
searching:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/documents/DOCUMENT_UUID
```

Search indexed chunks:

```bash
curl -X POST http://localhost:8000/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "query":"What does the document describe?",
    "limit":5
  }'
```

Ask a grounded question:

```bash
curl -X POST http://localhost:8000/qa/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "question":"What does the document describe?",
    "limit":5
  }'
```

Start a persistent conversation, then pass its ID to QA:

```bash
curl -X POST http://localhost:8000/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "title":"Architecture review"
  }'

curl -X POST http://localhost:8000/qa/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "conversation_id":"33333333-3333-3333-3333-333333333333",
    "question":"Can you summarize that in one sentence?",
    "limit":5
  }'
```

When `conversation_id` is omitted, `/qa/ask` remains stateless.

## RAG Evaluation

The repository includes a fully local keyword-based RAG evaluation pipeline.
It calls `/qa/ask`, checks expected facts in each answer, and reports passed,
failed, and accuracy percentage metrics.

```bash
python evaluation/run_eval.py \
  --knowledge-base-id YOUR_KNOWLEDGE_BASE_UUID \
  --access-token "$TOKEN"
```

Add cases in `evaluation/test_questions.json`. See
[RAG Evaluation](docs/EVALUATION.md) for dataset guidance, configuration, exit
codes, and metric limitations.

## Observability

Every HTTP request receives a generated `X-Request-ID`. Application and Uvicorn
logs are emitted as JSON to stdout, while AI/RAG operations report
`duration_ms` without logging document content, prompts, headers, or secrets.

```json
{
  "event": "request_completed",
  "request_id": "...",
  "status_code": 200,
  "duration_ms": 42.17
}
```

Set `LOG_LEVEL` in `.env` to control verbosity. See
[Observability](docs/OBSERVABILITY.md) for the event catalog, correlation flow,
privacy rules, and local `jq` command.

## Testing

The default pytest suite exercises health, request correlation, authentication,
tenant isolation, API contracts, orchestration, streaming, and metrics without
connecting to PostgreSQL, Qdrant, or LM Studio.

```bash
pytest
```

See [Testing](docs/TESTING.md) for focused commands, current coverage, dependency
overrides, and the infrastructure required by integration tests. The script
`scripts/verify_rag_e2e.py` is a deterministic simulation; use
`scripts/run_demo.py` against live services for an actual end-to-end flow.

## Code quality

Ruff checks application and test code for syntax/runtime errors, import order,
bug patterns, modernization opportunities, and async mistakes.

```bash
ruff check .
```

GitHub Actions runs a dependency audit, Ruff, pytest with live PostgreSQL and
Qdrant integration tests, and a production Docker build on every push and pull
request. The badge at the top of this README links directly to the repository
workflow. See [Continuous Integration](docs/CI.md) for pipeline details and
local reproduction commands.

## Repository structure

```text
app/
├── api/        # FastAPI routes and HTTP error mapping
├── core/       # Environment-backed application settings
├── db/         # Async SQLAlchemy engine, sessions, declarative base
├── llm/        # LM Studio/OpenAI-compatible provider client
├── models/     # SQLAlchemy persistence models
├── rag/        # Qdrant vector-store integration
├── schemas/    # Pydantic request and response contracts
├── services/   # Ingestion, search, health, and QA use cases
└── main.py     # Application composition and lifespan
migrations/     # Versioned Alembic database migrations
evaluation/     # Local RAG quality dataset and evaluation runner
examples/       # Demo-ready sample document
scripts/        # Local automation helpers, including the full demo runner
docs/
├── api-collection/
├── API_EXAMPLES.md
├── ARCHITECTURE.md
├── BACKLOG_PROCESS.md
├── CI.md
├── DATABASE.md
├── DEMO_FLOW.md
├── EVALUATION.md
├── GITHUB_SETUP.md
├── INTERVIEW.md
├── OBSERVABILITY.md
├── PORTFOLIO.md
├── RESUME.md
├── screenshots/
└── TESTING.md
tests/          # Fast async API and validation test suite
```

## Roadmap

For implementation-level planning, priorities, and acceptance criteria, see the
[project backlog](BACKLOG.md) and [backlog process](docs/BACKLOG_PROCESS.md).

### MVP — complete

- [x] Async API and PostgreSQL persistence
- [x] Versioned async Alembic migrations
- [x] User and knowledge-base ownership foundation
- [x] PDF/TXT extraction and overlapping chunking
- [x] LM Studio embeddings and chat completions
- [x] Dynamic Qdrant indexing with cosine distance
- [x] Semantic search
- [x] Knowledge-base-scoped retrieval filters
- [x] Context-grounded QA with sources
- [x] Persistent conversation memory and chat history
- [x] SSE answer streaming
- [x] Background document indexing with observable status
- [x] Offline keyword-based RAG evaluation pipeline
- [x] Structured logging, request correlation, and RAG timing events
- [x] Automated service-independent API contract tests
- [x] GitHub Actions CI with Ruff, pytest, and Docker validation

### V1 — production hardening

- [x] Infrastructure-backed integration tests in CI
- [ ] Durable Celery/Redis ingestion queue and upload-size limits
- [x] Document listing, retry, and deletion APIs
- [x] Knowledge base retrieval and cascading deletion APIs
- [x] Conversation listing and multi-turn session persistence
- [x] Prometheus metrics exporter and request correlation
- [ ] Embedding task prefixes and stale-vector detection after model changes

### V2 — platform capabilities

- [x] Hybrid retrieval (dense vectors + sparse text) and Reciprocal Rank Fusion (RRF)
- [x] Demo JWT authentication and user-level tenant checks
- [x] Multilingual Unicode-aware tokenization
- [x] Batch chunk embedding optimization
- [x] Structured SSE events with source citations
- [ ] Retrieval and answer quality evaluations
- [x] Pluggable LLM and embedding providers (OpenAI-compatible)
- [ ] Deployment profiles for local, staging, and production environments

## Current limitations

- Database migrations must be applied before starting a new environment.
- Document indexing jobs are durable in PostgreSQL. The default local API can
  run the worker in-process, while Docker Compose runs a separate worker
  container.
- Raw uploads use local filesystem storage and are not shared across replicas.
- Authentication is local demo JWT only; production password login, refresh
  tokens, OAuth, and organization roles are future work.
- Requests still identify the target knowledge base explicitly, but services
  verify that it belongs to the authenticated user.
- Answer quality depends on the selected local models and indexed documents.

## License

This project is licensed under the MIT License.
