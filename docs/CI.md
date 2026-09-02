# Continuous Integration

## Pipeline

GitHub Actions runs `.github/workflows/ci.yml` for every push and pull request.
The workflow uses an Ubuntu GitHub-hosted runner, checks out the repository,
installs Python 3.14, caches pip downloads, and installs the reproducible
`requirements.lock` environment.

The workflow grants the GitHub token only read access to repository contents.
Concurrent runs for the same branch or pull request are cancelled when a newer
commit arrives.

## Tests

The CI job runs on GitHub Actions with ephemeral PostgreSQL 17 and Qdrant
service containers. It applies database migrations and runs both fast API contract
tests and database/vector-store integration tests:

```bash
alembic upgrade head
RUN_INTEGRATION_TESTS=1 pytest -v
```

The fast suite uses HTTPX's in-process ASGI transport, while the integration
suite exercises real PostgreSQL migrations, multi-tenant persistence, and Qdrant
point payload filtering against the live service containers.

Before linting and tests, `pip-audit` checks the locked dependency set against
the Python Packaging Advisory Database, Bandit scans application code for
common security mistakes, and mypy checks application type contracts.

You can run the full suite locally with:

```bash
make test-integration
```

See [Testing](TESTING.md) for current coverage and integration test boundaries.

## Lint

Ruff configuration lives in `pyproject.toml`. CI runs:

```bash
ruff check .
```

The configured scope covers production code under `app/` and tests under
`tests/`. Versioned Alembic migrations and the standalone evaluation CLI are
excluded from this lint stage. Enabled rule families cover critical syntax and
runtime errors, import ordering, common bug patterns, Python upgrades, and
async-specific mistakes.

Run the same check locally before pushing:

```bash
ruff check .
ruff check . --fix
```

Review automatic fixes before committing them.

## Docker build

The final CI step validates the production image:

```bash
docker build --tag ai-rag-platform:ci .
```

This catches invalid Dockerfile instructions, unavailable Python 3.14 images,
Linux dependency/wheel problems, missing build files, and runtime-stage copy
errors. CI builds the image but does not publish it or start external services.

## Reproducing CI locally

From the repository root:

```bash
source venv/bin/activate
pip install -r requirements.lock
pip install bandit==1.9.4 mypy==1.18.2 pip-audit==2.10.1
pip-audit -r requirements.lock
bandit -r app -q
mypy app --ignore-missing-imports
ruff check .
ruff format --check .
pytest
docker build --tag ai-rag-platform:ci .
```

All commands must pass before the GitHub Actions job becomes green.
