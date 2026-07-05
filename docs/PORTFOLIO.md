# Portfolio Guide

## CV description

Short project line:

> Built a production-oriented, local-first RAG backend with FastAPI,
> PostgreSQL, Qdrant, and LM Studio, including asynchronous ingestion,
> knowledge-base-scoped retrieval, streaming chat, evaluation, observability,
> automated tests, Docker, and CI.

Resume bullets:

- Designed an async Python 3.14/FastAPI service that ingests PDF and TXT files,
  chunks extracted text, generates local embeddings, and indexes vectors in
  Qdrant.
- Implemented knowledge-base-scoped semantic search and grounded QA with source
  attribution, persistent conversations, and SSE token streaming.
- Modelled users, knowledge bases, documents, chunks, conversations, and
  messages in PostgreSQL with async SQLAlchemy and versioned Alembic migrations.
- Added document processing states, failure persistence, Qdrant compensation,
  JSON logs, request correlation, latency events, offline RAG evaluation, pytest
  contracts, Ruff, Docker Compose, and GitHub Actions CI.
- Kept inference fully local through LM Studio's OpenAI-compatible API, avoiding
  paid provider dependencies and API keys.

Choose two or three bullets that match the target role instead of pasting every
bullet into one CV entry.

## Interview talking points

### End-to-end request flow

Explain the system from upload to answer:

1. The upload API validates ownership and file type, stores raw data, creates a
   pending document row, and returns HTTP `202`.
2. A background task claims the document, extracts text, creates overlapping
   chunks, and flushes PostgreSQL IDs.
3. LM Studio generates embeddings; Qdrant stores vectors plus tenant-scoping
   payload; PostgreSQL records the final indexed or failed state.
4. Search embeds the question and applies a mandatory knowledge-base Qdrant
   filter.
5. QA constructs a strict system/history/context/question prompt and returns an
   answer with exact source chunks, either normally or over SSE.

### Failure handling

Discuss the PostgreSQL/Qdrant consistency boundary. They cannot share a single
transaction. Database changes remain uncommitted until vector indexing
succeeds. If Qdrant succeeds and the database commit fails, the service attempts
a compensating vector deletion. Failures become observable document states
rather than silently disappearing.

### RAG quality

The evaluator sends curated questions through the real QA endpoint and checks
case-insensitive expected keywords. This is intentionally transparent and
repeatable. It is a baseline, not a substitute for retrieval recall, grounded
faithfulness, human review, or model-based evaluation.

### Production engineering

Highlight boundaries, not only frameworks: thin HTTP routes, service
orchestration, provider adapters, async resource lifecycles, explicit
migrations, structured logs, request IDs, timing metrics, deterministic tests,
non-root containers, and CI quality gates.

## Architecture decisions

| Decision | Reason | Trade-off |
| --- | --- | --- |
| PostgreSQL plus Qdrant | Relational ownership/history and vector retrieval have different access patterns | Requires compensation across two data stores |
| LM Studio provider adapter | Local inference and model management through an OpenAI-compatible API | Availability and throughput depend on the developer machine |
| Knowledge-base payload filter | Enforces retrieval scope inside Qdrant, not only after search | Requires payload discipline and future authorization checks |
| Dynamic embedding dimensions | Allows model changes without hardcoded vector size | Existing collections must be re-indexed when dimensions change |
| FastAPI BackgroundTasks | Makes upload responsive without introducing Redis/Celery in the MVP | Jobs are not durable across API restarts |
| Overlapping character chunks | Simple, deterministic, and model-independent baseline | Token-aware or semantic chunking can improve retrieval quality |
| SSE streaming | Simple browser-compatible incremental delivery | No resume protocol or structured source events yet |
| Local filesystem uploads | Minimal local deployment complexity | Not suitable for horizontally scaled replicas |

## Scalability discussion

The current design is appropriate for a local portfolio MVP, not high-volume
multi-tenant production. A scaling path would include:

- replace `BackgroundTasks` with Celery, Dramatiq, or another durable queue;
- move raw files to S3-compatible object storage;
- batch and parallelize embeddings with bounded concurrency and provider rate
  limits;
- use separate API and worker deployments with independent autoscaling;
- introduce PostgreSQL connection-pool sizing, PgBouncer, and read/load
  monitoring;
- shard or replicate Qdrant and add payload indexes for tenant filters;
- add retrieval caching, hybrid dense/sparse search, metadata filters, and a
  reranker;
- enforce authenticated user/knowledge-base authorization on every operation;
- add quotas, upload-size limits, idempotency keys, retries, and dead-letter
  handling;
- export OpenTelemetry traces and Prometheus metrics with latency/error SLOs.

The local M1/8 GB target also constrains generation concurrency and model size.
In a hosted deployment the provider abstraction can point to a dedicated
inference server without moving provider-specific HTTP code into routes.

## Limitations and future work

Current limitations to state honestly:

- no JWT authentication or authorization enforcement;
- background jobs are in-process and non-durable;
- local uploads are not shared between replicas;
- embeddings are generated sequentially per document;
- retrieval uses dense similarity without reranking;
- keyword evaluation measures answer coverage, not full faithfulness;
- the fast CI suite does not yet run PostgreSQL/Qdrant/LM Studio integration
  tests;
- no document retry, deletion, or vector cleanup API;
- conversation context uses a fixed recent-message window rather than token
  budgeting or summarization.

Good next milestones are durable workers, authentication, integration tests,
object storage, batched embeddings, hybrid retrieval/reranking, structured SSE
events, and deeper RAG evaluation.

## Demo strategy

Use [Demo Flow](DEMO_FLOW.md) with the bundled sample document. Show the pending
to indexed transition, a Qdrant score, a grounded answer with sources, streaming
tokens, JSON timing logs, the evaluation report, and the green pytest/Ruff/CI
commands. This demonstrates the engineering system around the model, not only
one successful chat response.

## What not to claim

Do not describe this as a production SaaS already serving real users. Call it a
production-oriented portfolio implementation with explicit scaling paths. Do
not invent throughput, latency, accuracy, cost savings, user counts, or uptime;
measure and publish those numbers only after a reproducible benchmark exists.
