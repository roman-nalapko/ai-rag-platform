# Continuous Integration

## Pipeline

GitHub Actions runs `.github/workflows/ci.yml` for every push and pull request.
The workflow uses an Ubuntu GitHub-hosted runner, checks out the repository,
installs Python 3.14, caches pip downloads, and installs `requirements.txt`.

The workflow grants the GitHub token only read access to repository contents.
Concurrent runs for the same branch or pull request are cancelled when a newer
commit arrives.

## Tests

The CI job runs:

```bash
pytest
```

The default suite uses HTTPX's in-process ASGI transport and fake database
dependency, so CI does not start PostgreSQL, Qdrant, or LM Studio. Placeholder
environment values satisfy application configuration but are never contacted
by these tests. See [Testing](TESTING.md) for current coverage and integration
test boundaries.

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
pip install -r requirements.txt
ruff check .
pytest
docker build --tag ai-rag-platform:ci .
```

All four commands must pass before the GitHub Actions job becomes green.
