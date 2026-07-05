# RAG Evaluation

## Why evaluation matters

RAG quality depends on more than whether an LLM endpoint responds. Retrieval
must find the relevant chunks, the prompt must preserve their facts, and the
answer must contain the expected information. A repeatable evaluation dataset
makes regressions visible when chunking, embeddings, retrieval parameters,
prompts, or local models change.

The current evaluator is intentionally lightweight and fully local. It calls
the existing `/qa/ask` endpoint and checks whether every expected keyword is
present in the answer. It does not use paid APIs or an external judge model.

## Add test questions

Edit `evaluation/test_questions.json` and add objects with this structure:

```json
{
  "question": "What dependencies does the project use?",
  "expected_keywords": ["FastAPI", "PostgreSQL", "Qdrant"],
  "knowledge_base_id": "optional-placeholder"
}
```

`question` and `expected_keywords` are required. All keywords must be present
for the case to pass. Matching is case-insensitive. `knowledge_base_id` may be
a real UUID per case, or the whole dataset can use one runtime override.

Questions should target facts that actually exist in the indexed documents.
Prefer several focused cases over one broad question, and include terminology
whose presence can be checked without judging writing style.

## Run the evaluation

Start PostgreSQL, Qdrant, LM Studio, and FastAPI. Ensure the target knowledge
base has indexed documents, then run:

```bash
python evaluation/run_eval.py \
  --knowledge-base-id 22222222-2222-2222-2222-222222222222
```

Optional configuration:

```bash
python evaluation/run_eval.py \
  --questions evaluation/test_questions.json \
  --api-url http://localhost:8000 \
  --knowledge-base-id 22222222-2222-2222-2222-222222222222 \
  --limit 5 \
  --timeout 300
```

The 300-second default accommodates small local models on memory-constrained
Apple Silicon. Reduce it when your model and hardware are consistently faster.

The API URL and knowledge base can also be supplied through
`EVAL_API_URL` and `EVAL_KNOWLEDGE_BASE_ID`.

The command exits with code `0` when every case passes, `1` when any case
fails, and `2` for invalid evaluator configuration. This makes it suitable for
local quality gates and future CI jobs.

## Metrics

The report contains:

- `total_questions`: number of evaluated cases;
- `passed`: answers containing every expected keyword;
- `failed`: keyword misses, API failures, and unconfigured knowledge bases;
- `accuracy_percent`: `passed / total questions * 100`.

Keyword accuracy is a transparent MVP metric, not a complete measure of RAG
quality. Future versions can add retrieval recall, source relevance, grounded
answer checks, latency percentiles, and curated human scoring.
