# Testing

## Run the automated suite

Create the virtual environment and install the project dependencies, then run
pytest from the repository root:

```bash
source venv/bin/activate
pip install -r requirements.txt
pytest
```

Useful focused commands:

```bash
pytest tests/test_health.py
pytest tests/test_validation.py -v
pytest -k request_id
```

`pytest.ini` enables pytest-asyncio automatically, adds the repository root to
the Python import path, and limits discovery to `tests/`.

## Current coverage

The fast automated suite covers:

- the `/health` response contract;
- generation, UUID format, uniqueness, and propagation of `X-Request-ID`;
- user creation payload validation;
- knowledge-base creation payload validation;
- semantic-search request validation and limits;
- QA request validation, limits, and optional conversation UUID validation.

Tests use `httpx.AsyncClient` with `ASGITransport`, so requests exercise the
real FastAPI routing, middleware, dependency resolution, and Pydantic schemas
without starting a TCP server.

Validation tests override the database dependency with a sentinel object. A
valid `422` response therefore cannot connect to PostgreSQL. If invalid input
unexpectedly reaches a service, the sentinel fails the test immediately.
These tests also do not instantiate or call LM Studio or Qdrant.

## Integration environment

The following workflows require dedicated integration tests and real local
infrastructure:

- SQLAlchemy persistence and Alembic migrations: PostgreSQL 17;
- document background extraction and status transitions: PostgreSQL plus test
  upload storage;
- embeddings and answer generation: LM Studio with configured models;
- indexing and semantic retrieval: Qdrant and LM Studio;
- end-to-end upload, search, QA, conversation history, and SSE streaming: all
  services with an indexed knowledge base.

Start the infrastructure with:

```bash
docker compose up -d
alembic upgrade head
```

LM Studio remains a host process and must be started separately. The default
test suite intentionally excludes these integration workflows so it stays
fast, deterministic, and suitable for running on every code change.

## Adding tests

Place new files under `tests/` using the `test_*.py` naming convention. Prefer
API-contract tests for request/response validation, service tests with explicit
fakes for orchestration, and separately marked integration tests for real
PostgreSQL, Qdrant, filesystem, or LM Studio behavior.
