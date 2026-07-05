# Observability

## Structured JSON logging

The application writes one JSON object per line to stdout. This format can be
read locally, collected by Docker, or forwarded to systems such as Loki,
Elasticsearch, or a cloud log platform without changing application code.
Uvicorn's duplicate access log is disabled because it can include query
strings; the request middleware provides the canonical access event instead.

Configure the minimum level in `.env`:

```env
LOG_LEVEL=INFO
```

Example request completion record:

```json
{
  "timestamp": "2026-07-05T12:00:00.000000+00:00",
  "level": "INFO",
  "logger": "app.requests",
  "event": "request_completed",
  "request_id": "3b80ca4c-cb03-4776-a11e-248e6298e4df",
  "method": "POST",
  "path": "/qa/ask",
  "status_code": 200,
  "duration_ms": 842.31,
  "outcome": "completed"
}
```

For easier local inspection with `jq`:

```bash
uvicorn app.main:app --reload 2>&1 | jq -R 'fromjson? // .'
```

## Request correlation

The ASGI request middleware generates a new UUID for every HTTP request. The ID
is attached to all application logs emitted in that request context and is
returned to the caller as the `X-Request-ID` response header.

```bash
curl --include http://localhost:8000/health
```

Request logging emits:

- `request_started` with `method` and `path`;
- `request_completed` with `status_code` and full response `duration_ms`;
- `request_failed` for unhandled application exceptions.

The middleware operates at ASGI message level, so completion timing includes
the complete response body and works with the SSE streaming endpoint.

## AI and RAG timings

Operational timing events include:

| Event | Measurement |
| --- | --- |
| `embedding_completed` | One LM Studio embedding request |
| `qdrant_search_completed` | Collection check and vector search |
| `lm_generation_completed` | Full normal or streaming generation |
| `document_indexing_completed` | Extraction through final indexed DB commit |

Failure variants use the corresponding `*_failed` event. Timing records carry
`duration_ms`, `operation`, and `outcome`. Where useful, they also include safe
metadata such as document/knowledge-base UUIDs, chunk count, embedding
dimensions, result count, and search limit.

Embedding timing is emitted per text because the current local indexing flow
requests embeddings sequentially. This makes model latency and large-document
cost visible independently from total document indexing time.

## Privacy and secret handling

The JSON formatter uses an explicit field whitelist. The application does not
log:

- request or response bodies;
- query strings or HTTP headers;
- document/chunk content or vectors;
- questions, prompts, retrieved context, or generated answers;
- database URLs, API keys, environment variables, or authorization values.

For exception records, only `exception_type` is serialized. Provider exception
messages and tracebacks are intentionally excluded because they may contain
remote response details. Keep new logging calls metadata-only and never attach
raw model inputs through `extra` fields.

## Current scope

This step provides structured logs, request correlation, and latency signals.
Metrics scraping, distributed tracing, dashboards, alerting, and retention
policies remain deployment concerns for a future production profile.
