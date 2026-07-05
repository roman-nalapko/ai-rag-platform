# AI RAG Platform — Production RAG Backend

[![CI](https://github.com/roman-nalapko/ai-rag-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/roman-nalapko/ai-rag-platform/actions/workflows/ci.yml)

Production-oriented, local-first RAG backend powered by LM Studio local models.
Multi-tenant knowledge bases isolate ingestion, retrieval, and conversation data.
Grounded question answering supports source attribution and SSE streaming chat.
An offline evaluation pipeline measures answer quality against expected facts.
Docker Compose and GitHub Actions make the complete stack reproducible and CI-ready.

**Portfolio links:** [guided demo](docs/DEMO_FLOW.md) ·
[architecture](docs/ARCHITECTURE.md) · [portfolio/interview guide](docs/PORTFOLIO.md) ·
[API examples](docs/API_EXAMPLES.md)

## Quick start

Prerequisites: Docker Desktop and LM Studio with one chat model and one
embedding model. Enable LM Studio's Local Server on port `1234` and local
network access, then:

```bash
cp .env.example .env
# Set the exact LM_STUDIO_CHAT_MODEL and LM_STUDIO_EMBEDDING_MODEL IDs in .env

docker compose up -d postgres qdrant
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d api

curl http://localhost:8000/health
```

Open [Swagger UI](http://localhost:8000/docs), then follow the
[eight-step demo](docs/DEMO_FLOW.md) using `examples/sample_document.txt`.

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
    | tenant data + chat |            | vectors + payload  |
    +--------------------+            +--------------------+
```

The HTTP layer validates requests and maps errors. Services orchestrate use
cases. Provider-specific LM Studio and Qdrant operations remain isolated in
`llm/` and `rag/`. See [Architecture](docs/ARCHITECTURE.md) for the detailed
module and data-flow description.

## Screenshots

Replace these links with real captures as the public demo evolves:

- [API Documentation (FastAPI Swagger)](docs/screenshots/api-documentation.png)
- [Qdrant Vector Dashboard](docs/screenshots/qdrant-vector-dashboard.png)
- [RAG Chat Flow](docs/screenshots/rag-chat-flow.png)
- [Evaluation Report](docs/screenshots/evaluation-report.png)

## Tech stack

| Area | Technology |
| --- | --- |
| Language | Python 3.14 |
| API | FastAPI, Pydantic v2, Uvicorn |
| Database | PostgreSQL 17, SQLAlchemy async, asyncpg |
| Vector store | Qdrant, async Qdrant client, cosine distance |
| Local AI | LM Studio, OpenAI-compatible API, official OpenAI Python SDK |
| Document processing | pypdf, UTF-8 text extraction |
| Infrastructure | Docker Compose |

## Key features

- **RAG ingestion:** PDF/TXT extraction, overlapping chunks, local embeddings,
  dynamic Qdrant collections, and observable processing states.
- **Scoped retrieval:** top-K cosine search with mandatory knowledge-base
  payload filters, scores, and complete source metadata.
- **Grounded chat:** strict context-only prompting, deterministic fallback,
  source attribution, persistent conversation history, and SSE streaming.
- **SaaS foundation:** users, knowledge bases, documents, chunks,
  conversations, and messages modelled in PostgreSQL with cascade rules.
- **Failure handling:** explicit provider errors, failed-document diagnostics,
  transactional chunk writes, and compensating Qdrant deletion.
- **Quality engineering:** offline RAG evaluation, pytest API contracts, Ruff,
  GitHub Actions, and a reproducible sample document/demo.
- **Observability:** JSON logs, `X-Request-ID`, and embedding, retrieval,
  generation, and indexing latency events without logging model inputs.
- **Local deployment:** LM Studio inference with no paid key, versioned Alembic
  migrations, and a non-root Python 3.14 Docker image.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API process health |
| `GET` | `/health/llm` | LM Studio embedding health and dimensions |
| `POST` | `/users` | Create a user account record |
| `POST` | `/knowledge-bases` | Create a user-owned knowledge base |
| `GET` | `/knowledge-bases?user_id=...` | List one user's knowledge bases |
| `POST` | `/conversations` | Start a conversation in a knowledge base |
| `GET` | `/conversations/{id}/messages` | Read a conversation's chat history |
| `POST` | `/documents/upload` | Store a PDF/TXT file and enqueue indexing |
| `GET` | `/documents/{id}` | Read processing status, chunk count, and errors |
| `POST` | `/search` | Semantic search within one knowledge base |
| `POST` | `/qa/ask` | Knowledge-base-scoped RAG answer with sources |
| `POST` | `/qa/ask/stream` | Stream a grounded answer over SSE |

Interactive documentation is available at
[http://localhost:8000/docs](http://localhost:8000/docs) while the API is
running. Complete curl requests are in [API Examples](docs/API_EXAMPLES.md).

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
pip install -r requirements.txt
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
   UPLOAD_STORAGE_PATH=storage/uploads
   ```

   On an 8 GB M1, load the chat model with a 2048-token context and one
   parallel request. The longer API timeout is intentional: memory pressure
   can make even short local completions take more than 30 seconds.

The API key is a local placeholder unless authentication is explicitly enabled
inside LM Studio. Embedding dimensions are discovered dynamically; the current
Nomic configuration returns 768-dimensional vectors.

### 5. Start FastAPI

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify the services:

```bash
curl http://localhost:8000/health
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
   docker compose up -d api
   docker compose ps
   curl http://localhost:8000/health
   ```

Follow structured logs or stop the stack:

```bash
docker compose logs -f api
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

Create a user and then a knowledge base:

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email":"engineer@example.com"}'

curl -X POST http://localhost:8000/knowledge-bases \
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
  -F "knowledge_base_id=22222222-2222-2222-2222-222222222222" \
  -F "file=@examples/sample_document.txt;type=text/plain"
```

The upload returns HTTP `202` with `status: "pending"`. Poll its status before
searching:

```bash
curl http://localhost:8000/documents/DOCUMENT_UUID
```

Search indexed chunks:

```bash
curl -X POST http://localhost:8000/search \
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
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "title":"Architecture review"
  }'

curl -X POST http://localhost:8000/qa/ask \
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
  --knowledge-base-id YOUR_KNOWLEDGE_BASE_UUID
```

Add cases in `evaluation/test_questions.json`. See
[RAG Evaluation](docs/EVALUATION.md) for dataset guidance, configuration, exit
codes, and metric limitations.

## Observability

Every HTTP request receives a generated `X-Request-ID`. Application and Uvicorn
logs are emitted as JSON to stdout, while AI/RAG operations report
`duration_ms` without logging document content, prompts, headers, or secrets.

```json
{"event":"request_completed","request_id":"...","status_code":200,"duration_ms":42.17}
```

Set `LOG_LEVEL` in `.env` to control verbosity. See
[Observability](docs/OBSERVABILITY.md) for the event catalog, correlation flow,
privacy rules, and local `jq` command.

## Testing

The default pytest suite exercises health, request correlation, and API request
validation without connecting to PostgreSQL, Qdrant, or LM Studio.

```bash
pytest
```

See [Testing](docs/TESTING.md) for focused commands, current coverage, dependency
overrides, and the infrastructure required by future integration tests.

## Code quality

Ruff checks application and test code for syntax/runtime errors, import order,
bug patterns, modernization opportunities, and async mistakes.

```bash
ruff check .
```

GitHub Actions runs Ruff, pytest, and a production Docker build on every push
and pull request. The badge at the top of this README links directly to the
repository workflow. See [Continuous Integration](docs/CI.md) for pipeline
details and local reproduction commands.

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
docs/
├── API_EXAMPLES.md
├── ARCHITECTURE.md
├── CI.md
├── DATABASE.md
├── DEMO_FLOW.md
├── EVALUATION.md
├── GITHUB_SETUP.md
├── OBSERVABILITY.md
├── PORTFOLIO.md
├── screenshots/
└── TESTING.md
tests/          # Fast async API and validation test suite
```

## Roadmap

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

- [ ] Infrastructure-backed integration tests in CI
- [ ] Durable Celery/Redis ingestion queue and upload-size limits
- [ ] Document listing, retry, and deletion APIs
- [ ] Metrics, distributed tracing, dashboards, alerts, and retry policies
- [ ] Embedding task prefixes, re-indexing, and model-version metadata

### V2 — platform capabilities

- [ ] Hybrid dense/sparse retrieval and reranking
- [ ] Authentication, authorization, and multi-tenancy
- [ ] Structured SSE events with source metadata and resume support
- [ ] Retrieval and answer quality evaluations
- [ ] Pluggable LLM and embedding providers
- [ ] Deployment profiles for local, staging, and production environments

## Current limitations

- Database migrations must be applied before starting a new environment.
- Background indexing uses FastAPI `BackgroundTasks` in the API process. Jobs
  are not durable across process crashes; Celery/Redis is planned for V1.
- Raw uploads use local filesystem storage and are not shared across replicas.
- The API has no authentication and is intended for local development.
- Requests identify the target knowledge base explicitly until authenticated
  tenant context is introduced.
- Answer quality depends on the selected local models and indexed documents.

## License

No license has been selected yet. Add a license before public redistribution or
external contributions.
