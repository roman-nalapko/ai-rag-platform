# Contributing to AI RAG Platform

Thank you for your interest in contributing to the **Local AI RAG Platform**! We welcome bug reports, improvements, documentation updates, and feature contributions.

## Development Workflow

### 1. Prerequisites

- Python 3.14+
- Docker & Docker Compose
- LM Studio / Ollama (for local LLM inference)

### 2. Local Setup

```bash
# Clone the repository
git clone https://github.com/roman-nalapko/ai-rag-platform.git
cd ai-rag-platform

# Create virtual environment and install dependencies
python3.14 -m venv venv
source venv/bin/activate
make install

# Copy environment template
cp .env.example .env

# Start backing services (PostgreSQL & Qdrant)
make docker-up

# Apply database migrations
make migrate
```

### 3. Running Quality Checks

Before submitting a pull request, ensure all checks pass:

```bash
# Format and lint
make format
make lint

# Run fast unit/contract tests
make test

# Run infrastructure integration tests (requires docker-up)
make test-integration
```

### 4. Making Changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Write clean, modular code with type annotations and docstrings.
3. Add unit or contract tests under `tests/` for new endpoints or logic.
4. If database schema changes are required, generate a migration with Alembic:
   ```bash
   venv/bin/alembic revision -m "description_of_change"
   ```
5. Ensure no secrets, `.env` files, or binary artifacts are committed.

### 5. Pull Request Guidelines

- Provide a clear PR title and description explaining what was changed and why.
- Link any relevant issues or backlog items.
- Verify that GitHub Actions CI is completely green.
