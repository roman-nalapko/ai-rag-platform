# Changelog

All notable changes to the **AI RAG Platform** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-26

### Added

- **Structured SSE Streaming with Instant Citations**:
  - `POST /qa/ask/stream` emits structured Server-Sent Events (`event: sources`, `event: token`, `event: done`, `data: [DONE]`).
  - Source chunk metadata and relevance scores are streamed before generation tokens begin.
  - Interactive Web Demo UI (`/demo/`) renders live citation cards real-time during streaming.
- **Hybrid Retrieval & Reciprocal Rank Fusion (RRF)**:
  - Added `reciprocal_rank_fusion` in `app.rag.fusion` combining Qdrant dense vectors with PostgreSQL full-text search (`to_tsvector`/`plainto_tsquery`).
  - Added `search_text` and `search_hybrid` methods to `SearchService`.
- **Prometheus Metrics Exporter & Observability**:
  - Built-in zero-dependency Prometheus metrics registry (`app.core.metrics`) exposing `GET /metrics` (`text/plain; version=0.0.4`).
  - Automatic request counting, latency histograms, semantic search timings, LLM inference durations, and background worker throughput.
  - Request correlation middleware attaching unique `X-Request-ID` headers to all responses and structured JSON logs.
- **Multi-Provider LLM & Embedding Client**:
  - Extensible `LLMClient` protocol and `get_llm_client()` factory with `OpenAICompatibleClient` supporting LM Studio, Ollama, OpenAI, vLLM, and LocalAI.
  - Batched chunk embeddings (`embed_texts`) for fast ingestion of large documents.
- **CI Integration Testing with Ephemeral Services**:
  - GitHub Actions workflow running `postgres:17-alpine` and `qdrant/qdrant:latest` service containers.
  - Automated migration execution and `RUN_INTEGRATION_TESTS=1 pytest -v` validation on every pull request and push.
- **Complete Multi-Tenant Resource Lifecycle APIs**:
  - `GET /documents` with chunk counts and paginated filters.
  - `GET /conversations` for listing active chat sessions in a knowledge base.
  - `GET /knowledge-bases/{id}` and cascading `DELETE /knowledge-bases/{id}` with cleanup across PostgreSQL, local storage, and Qdrant points.
  - `POST /documents/{id}/reindex` and `DELETE /documents/{id}`.
- **Multilingual Unicode Reranker**:
  - `KeywordOverlapReranker` updated with `\w+` Unicode regex for Cyrillic and international text support.
- **Zero-Config Developer Experience**:
  - Pre-configured test environment fallbacks in `tests/conftest.py` allowing instant `pytest` execution on clean repository clones.
- **Tooling & API Collections**:
  - Bruno API collection in `docs/api-collection/AI-RAG-Platform/`.
  - Upgraded `Makefile` with `make format`, `make lint`, `make test`, `make test-integration`, `make demo`.
  - Expanded offline evaluation dataset in `evaluation/test_questions.json`.

### Changed

- Hardened `DocumentWorker` error recovery with `try...finally` state guarantees.
- Synchronized all technical documentation: `README.md`, `BACKLOG.md`, `docs/OBSERVABILITY.md`, `docs/CI.md`, `docs/API_EXAMPLES.md`.

### Fixed

- Fixed cross-tenant document, conversation, and knowledge-base authorization checks across all endpoints.
- Fixed stream cancellation resource leaks with explicit async generator cleanup.
