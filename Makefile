SHELL := /bin/bash

VENV ?= venv
PYTHON ?= $(VENV)/bin/python
PIP ?= $(VENV)/bin/pip
PYTEST ?= $(VENV)/bin/pytest
RUFF ?= $(VENV)/bin/ruff
ALEMBIC ?= $(VENV)/bin/alembic
UVICORN ?= $(VENV)/bin/uvicorn

API_HOST ?= 0.0.0.0
API_PORT ?= 8000
API_URL ?= http://localhost:8000
KNOWLEDGE_BASE_ID ?=

.PHONY: help install lint test check migrate migrate-docker run docker-build docker-up docker-api-up docker-down docker-logs health health-llm eval demo-flow

help:
	@echo "AI RAG Platform commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install         Install Python dependencies into venv"
	@echo "  make migrate         Apply Alembic migrations locally"
	@echo "  make migrate-docker  Apply Alembic migrations through Docker Compose"
	@echo ""
	@echo "Quality:"
	@echo "  make lint            Run Ruff"
	@echo "  make test            Run pytest"
	@echo "  make check           Run lint and tests"
	@echo ""
	@echo "Run:"
	@echo "  make docker-up       Start PostgreSQL and Qdrant"
	@echo "  make docker-api-up   Build and start API container"
	@echo "  make docker-down     Stop Docker Compose services"
	@echo "  make run             Run FastAPI locally with reload"
	@echo ""
	@echo "Demo:"
	@echo "  make health          Check API health"
	@echo "  make health-llm      Check LM Studio embedding health"
	@echo "  make eval KNOWLEDGE_BASE_ID=<uuid>"
	@echo "  make demo-flow       Print guided demo path"

install:
	$(PIP) install -r requirements.txt

lint:
	$(RUFF) check .

test:
	$(PYTEST)

check: lint test

migrate:
	$(ALEMBIC) upgrade head

migrate-docker:
	docker compose run --rm api alembic upgrade head

run:
	$(UVICORN) app.main:app --reload --host $(API_HOST) --port $(API_PORT)

docker-build:
	docker compose build api

docker-up:
	docker compose up -d postgres qdrant

docker-api-up:
	docker compose up -d --build api

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

health:
	curl --silent --show-error "$(API_URL)/health"

health-llm:
	curl --silent --show-error "$(API_URL)/health/llm"

eval:
	@test -n "$(KNOWLEDGE_BASE_ID)" || (echo "Set KNOWLEDGE_BASE_ID=<uuid>" && exit 1)
	$(PYTHON) evaluation/run_eval.py --knowledge-base-id "$(KNOWLEDGE_BASE_ID)"

demo-flow:
	@echo "Follow docs/DEMO_FLOW.md"
	@echo "Sample document: examples/sample_document.txt"
	@echo "Swagger UI: $(API_URL)/docs"
