# Deployment Profile

AI RAG Platform is intentionally local-first, but the backend can be deployed
as a small production-style stack when the LLM provider exposes an
OpenAI-compatible API.

## Recommended small-cloud topology

```text
HTTPS
  |
  v
API container(s)  --->  managed PostgreSQL
  |
  +-------------->  worker container(s)
  |
  +-------------->  managed Qdrant or Qdrant VM
  |
  +-------------->  OpenAI-compatible LLM endpoint
```

Use one API container and one worker container for a small demo deployment.
Scale the worker independently when document ingestion becomes slower than
interactive Search/QA traffic.

## Required runtime environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy URL for PostgreSQL, for example `postgresql+asyncpg://...` |
| `QDRANT_URL` | HTTP URL for Qdrant |
| `UPLOAD_STORAGE_PATH` | Local path mounted for raw uploads |
| `UPLOAD_MAX_BYTES` | Maximum accepted upload size |
| `LM_STUDIO_BASE_URL` | OpenAI-compatible `/v1` endpoint |
| `LM_STUDIO_API_KEY` | Provider key or local placeholder |
| `LM_STUDIO_CHAT_MODEL` | Chat/instruct model ID |
| `LM_STUDIO_EMBEDDING_MODEL` | Embedding model ID |
| `LM_STUDIO_TIMEOUT_SECONDS` | Timeout for local or remote model calls |
| `LM_STUDIO_MAX_TOKENS` | Maximum generated answer tokens |
| `JWT_SECRET_KEY` | Strong secret for signing local JWTs |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime |
| `DOCUMENT_WORKER_ENABLED` | `false` for API containers when a separate worker runs |
| `DOCUMENT_WORKER_POLL_SECONDS` | Queue polling interval |
| `RERANKING_ENABLED` | Enable optional local keyword-overlap reranking |
| `RERANKING_CANDIDATE_MULTIPLIER` | Qdrant over-fetch multiplier for reranking |
| `LOG_LEVEL` | JSON log verbosity |

## Deployment steps

1. Provision PostgreSQL 17 and Qdrant.
2. Build the Docker image from the repository root.
3. Run `alembic upgrade head` once against the target database.
4. Start the API container with `DOCUMENT_WORKER_ENABLED=false`.
5. Start at least one worker container with `python -m app.worker`.
6. Mount shared upload storage at `UPLOAD_STORAGE_PATH` for both API and worker
   containers.
7. Configure the LLM endpoint and model IDs.
8. Put the API behind HTTPS and restrict direct database/Qdrant access.

## Security limitations

- Current auth is local demo JWT only. Production deployments should add
  password login, refresh-token rotation, account recovery, organization roles,
  and audit logs.
- Raw uploads are stored on a local/shared filesystem. Production deployments
  should move them to object storage with lifecycle policies.
- The `/demo` UI is useful for demos, but production deployments may want to
  disable it or protect it behind the same frontend auth layer.
- `JWT_SECRET_KEY` must be a real secret from a secrets manager, not the
  `.env.example` placeholder.

## Cost and operations limitations

- Running local LM Studio is cost-free but tied to one machine. A hosted
  OpenAI-compatible inference endpoint improves availability but may introduce
  GPU/server costs.
- PostgreSQL-backed jobs are durable and simple, but high-throughput ingestion
  should move to a broker-backed queue such as Redis/Celery, Dramatiq, or
  RabbitMQ.
- Local filesystem uploads are not safe for multi-replica deployments unless
  the path is backed by shared persistent storage.
- Add metrics, tracing, backups, and alerts before treating this as a
  production service.
