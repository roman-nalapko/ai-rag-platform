# Architecture

## Overview

AI RAG Platform follows a layered architecture with explicit boundaries between
HTTP transport, application orchestration, persistence, vector operations, and
local model inference.

```text
HTTP request
    |
    v
api/  -- validates and maps HTTP errors
    |
    v
services/  -- orchestrates application use cases
    |                 |                    |
    v                 v                    v
db/ + models/       rag/                 llm/
PostgreSQL          Qdrant               LM Studio
    ^                 ^                    ^
    +-----------------+--------------------+
             schemas define API contracts
```

Dependency direction is inward from routes to services. Business workflows do
not live in FastAPI route functions. Provider-specific calls do not leak into
the HTTP layer.

## Docker deployment topology

```text
Host machine
├── LM Studio :1234
│       ^
│       | host.docker.internal
│       |
└── Docker Compose network
    ├── api :8000
    │   └── uploads_data -> /app/storage/uploads
    ├── postgres :5432 -> postgres_data
    └── qdrant :6333/:6334 -> qdrant_data
```

The API resolves PostgreSQL and Qdrant through Docker service DNS. LM Studio is
deliberately not containerized: it runs on the developer host and is reached at
`http://host.docker.internal:1234/v1`. Compose adds the corresponding
`host-gateway` mapping for Linux compatibility; Docker Desktop provides it on
macOS.

The API image is built from `python:3.14-slim` in two stages. Dependencies are
installed into a virtual environment in the builder stage, then copied with the
application and Alembic files into a smaller runtime stage. Uvicorn runs as a
non-root system user and exposes port `8000`.

## Modules

### `app/api`

The API layer owns HTTP concerns:

- Route registration and status codes
- FastAPI dependency injection
- Request/response schema selection
- Mapping application exceptions to HTTP errors
- Closing uploaded files

Routes delegate ingestion, search, health checks, and QA orchestration to
services. They do not call PostgreSQL, Qdrant, or the OpenAI-compatible API
directly.

### `app/services`

The service layer contains application use cases:

- `document.py` persists upload metadata and raw files, claims pending jobs,
  coordinates extraction/chunking/indexing, and exposes processing status.
- `text_extraction.py` decodes UTF-8 TXT files and extracts PDF text with
  `pypdf`. PDF parsing is moved off the event loop.
- `chunking.py` creates overlapping text chunks.
- `search.py` generates a query embedding, invokes vector search, and maps
  Qdrant payloads into typed search matches.
- `qa.py` retrieves source chunks, builds a bounded context, applies the
  grounding prompt, loads optional conversation memory, invokes the chat model,
  and persists the completed exchange.
- `conversation.py` creates knowledge-base-scoped conversations, reads ordered
  history, and writes user/assistant message pairs transactionally.
- `llm_health.py` verifies the configured embedding model and reports its
  dynamic dimensions.

Services translate provider failures into application-level exceptions so the
API layer can distinguish LM Studio unavailability from Qdrant failures.

### `app/rag`

The RAG infrastructure layer currently contains `vector_store.py`. It owns all
Qdrant-specific behavior:

- Async Qdrant client lifecycle
- Automatic `document_chunks` collection creation
- Dynamic vector-size discovery from the first embedding
- Cosine-distance configuration validation
- Chunk payload construction, including knowledge-base ownership, and batched
  upsert
- Semantic `query_points` calls with mandatory knowledge-base payload filters
- Deletion and best-effort compensation

The stored payload includes knowledge base ID, document ID, chunk ID, chunk
index, filename, and chunk content. Qdrant response types are converted into
neutral application objects before returning to services.

### `app/llm`

The LLM layer isolates the LM Studio provider behind `LMStudioClient`.

LM Studio exposes an OpenAI-compatible local API. The client uses the official
async OpenAI Python SDK with a custom base URL and provides three operations:

- `embed_text(text)`
- `chat_completion(prompt, context, history, system_prompt)`
- `stream_chat_completion(prompt, context, history, system_prompt)`

The client validates empty responses, wraps SDK failures, reuses its HTTP
connection pool, and closes it during application shutdown.

### `app/db`

The database layer provides:

- SQLAlchemy declarative base and naming conventions
- Async engine backed by `asyncpg`
- `async_sessionmaker`
- FastAPI session dependency
- Engine disposal during application shutdown

Versioned Alembic migrations own all schema changes. The application never
creates or alters tables during startup. See [Database](DATABASE.md).

### `app/models`

SQLAlchemy models define the relational persistence model:

- `Document` stores upload metadata and processing state.
- `DocumentChunk` stores ordered extracted text and references its document.
- `User` is the root owner for future tenant authentication.
- `KnowledgeBase` groups documents under one user.
- `Conversation` scopes a persistent chat to one knowledge base.
- `Message` stores ordered `user` and `assistant` turns.

Ownership foreign keys use database cascades from users to knowledge bases, from
knowledge bases to documents or conversations, from documents to chunks, and
from conversations to messages. A unique constraint protects
`(document_id, chunk_index)` ordering; a check constraint protects message roles.

### `app/schemas`

Pydantic v2 schemas define public API contracts independently from ORM and
provider models. They validate:

- Upload responses
- Search requests and results
- QA requests, answers, and source attribution
- Health responses

String inputs are normalized, collection limits are bounded, and unknown fields
are rejected for search and QA requests.

## Ingestion flow

```text
POST /documents/upload
    -> validate filename and media type
    -> validate destination knowledge base
    -> persist raw file under storage/uploads/<document-id>.<extension>
    -> create Document(status=pending)
    -> schedule FastAPI BackgroundTask
    -> return HTTP 202

Background task (independent database session)
    -> atomically claim pending document as processing
    -> extract TXT/PDF text
    -> split into overlapping chunks
    -> stage DocumentChunk rows
    -> flush PostgreSQL IDs
    -> embed every chunk through LM Studio
    -> create/validate Qdrant collection
    -> upsert vectors and payloads
    -> mark document indexed
    -> commit PostgreSQL transaction

On failure
    -> roll back uncommitted chunks
    -> compensate completed Qdrant upsert when necessary
    -> mark document failed and persist a safe error_message
```

PostgreSQL and Qdrant cannot share a distributed transaction. If Qdrant
indexing fails, the database transaction is rolled back. If Qdrant succeeds but
the database commit fails, the service attempts to remove the document vectors
as compensation. Compensation failures are logged instead of hiding the
original database error.

FastAPI `BackgroundTasks` is intentionally an interim worker mechanism. It
runs after the response in the API process and is not durable if that process
stops. The state machine makes progress observable, but a durable queue and
retry policy remain future work.

## Semantic search flow

```text
POST /search
    -> validate knowledge base ID, query, and limit
    -> verify the knowledge base exists in PostgreSQL
    -> generate query embedding through LM Studio
    -> query Qdrant with cosine similarity and knowledge-base filter
    -> validate payload fields
    -> return ranked chunks and scores
```

Search returns an empty result when no collection exists. LM Studio failures
map to HTTP `503`; Qdrant failures map to HTTP `500`.

## Question-answering flow

```text
POST /qa/ask or /qa/ask/stream
    -> optionally validate conversation belongs to the knowledge base
    -> load its last five messages in chronological order
    -> reuse knowledge-base-scoped semantic search
    -> format top chunks as labelled context
    -> build prompt: system rules, history, context, latest question
    -> call or stream LM Studio chat completion
    -> persist the user question and assistant answer when conversation_id exists
    -> return answer and the exact source chunks
```

The prompt instructs the model to use only supplied context, treat document
text as untrusted reference data, avoid invented facts, and return a fixed
fallback sentence when evidence is insufficient. With no search results, the
fallback is returned without invoking the chat model and is still persisted as
the assistant turn when conversation memory is enabled. Omitting
`conversation_id` preserves stateless QA behavior.

## Runtime lifecycle

Before application deployment, `alembic upgrade head` applies pending schema
migrations. Provider clients are created lazily and cached per process. FastAPI
shutdown closes Qdrant, LM Studio, and SQLAlchemy connection pools in that
order.

For the full container profile, migrations run through a one-off API container
before the long-running API service starts. Schema creation remains outside the
application startup lifecycle. The API healthcheck calls `/health`; PostgreSQL
must pass `pg_isready`, while Qdrant must at least be started before Compose
starts the API.

PostgreSQL, Qdrant, and FastAPI run in Docker Compose. LM Studio remains on the
host machine because it manages Apple Silicon model execution. Named volumes
preserve relational data, vectors, and raw uploads independently of container
replacement.
