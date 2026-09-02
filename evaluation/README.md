# Evaluation Guide

This directory contains the RAG evaluation suite for `ai-rag-platform`.

## Overview

Two evaluation modes are supported:

| Mode | Description |
|---|---|
| `keyword` | (default) Checks that expected keywords appear in the answer |
| `llm-judge` | Sends each answer to an LLM and asks it to score faithfulness 0–10 |

## Quick Start

### Prerequisites

1. The API must be running: `make docker-up && uvicorn app.main:app --reload`
2. A knowledge base must exist with at least one indexed document (e.g. `examples/sample_document.txt`)
3. A valid bearer token must be available

### Run keyword evaluation

```bash
python evaluation/run_eval.py \
  --knowledge-base-id <your-kb-uuid> \
  --access-token <your-jwt-token>
```

### Run LLM-judge evaluation

```bash
python evaluation/run_eval.py \
  --mode llm-judge \
  --knowledge-base-id <your-kb-uuid> \
  --access-token <your-jwt-token> \
  --llm-url http://localhost:1234/v1 \
  --llm-model your-model-name \
  --llm-min-score 6.0
```

## Environment Variables

All CLI flags can also be set via environment variables:

| Variable | CLI flag | Default |
|---|---|---|
| `EVAL_API_URL` | `--api-url` | `http://localhost:8000` |
| `EVAL_KNOWLEDGE_BASE_ID` | `--knowledge-base-id` | *(required)* |
| `EVAL_ACCESS_TOKEN` | `--access-token` | *(required for protected endpoints)* |
| `EVAL_MODE` | `--mode` | `keyword` |
| `EVAL_LLM_URL` | `--llm-url` | `http://localhost:1234/v1` |
| `EVAL_LLM_MODEL` | `--llm-model` | `""` (auto-detected) |
| `EVAL_LLM_MIN_SCORE` | `--llm-min-score` | `6.0` |

## Test Questions

`test_questions.json` contains 12 questions covering:

- Dependency and technology stack questions (PostgreSQL, Qdrant, FastAPI)
- Document format questions (TXT, PDF)
- Document lifecycle questions (pending → processing → indexed)
- Multi-tenancy and streaming questions
- **Hallucination guards** — questions about topics not in the dataset that should return "I don't have enough information"

### Adding questions

Each question follows this schema:

```json
{
  "question": "What databases does the project use?",
  "expected_keywords": ["PostgreSQL", "Qdrant"],
  "expected_source_keywords": ["PostgreSQL", "Qdrant"],
  "expected_source_filenames": ["sample_document.txt"],
  "knowledge_base_id": "optional-placeholder"
}
```

Set `knowledge_base_id` to `"optional-placeholder"` to use the `--knowledge-base-id` CLI argument (recommended), or embed a real UUID directly.

## Keyword Mode — How it works

1. Calls `POST /qa/ask` for each question
2. Checks that all `expected_keywords` appear (case-insensitive) in the answer text
3. Checks that `expected_source_keywords` appear in retrieved chunks
4. Checks that `expected_source_filenames` appear in the sources

## LLM-Judge Mode — How it works

1. Calls `POST /qa/ask` for each question (same as keyword mode)
2. Sends the question + retrieved context + answer to the LLM with the prompt:
   ```
   Score the answer on faithfulness and relevance from 0 to 10.
   SCORE: <integer 0-10>
   REASON: <one sentence>
   ```
3. A case passes if `score >= llm-min-score` (default: 6.0)

LLM-judge is more robust for semantic evaluation but requires LM Studio (or another OpenAI-compatible endpoint) to be running.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | All cases passed |
| `1` | One or more cases failed |
| `2` | Configuration error (bad arguments, missing dataset) |
