# Demo Flow

This walkthrough demonstrates the complete local RAG lifecycle using
`examples/sample_document.txt`. It assumes the API is available at
`http://localhost:8000`, LM Studio is running, migrations are applied, and
`jq` is installed for extracting IDs from JSON.

## 1. Create a user

```bash
USER_RESPONSE=$(curl --silent --show-error \
  -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email":"portfolio-demo@example.com"}')

echo "$USER_RESPONSE" | jq
USER_ID=$(echo "$USER_RESPONSE" | jq -r '.id')
```

Use a different email if the demo user already exists.

## 2. Create a knowledge base

```bash
KB_RESPONSE=$(curl --silent --show-error \
  -X POST http://localhost:8000/knowledge-bases \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"name\": \"AI RAG Platform Demo\",
    \"description\": \"Portfolio demonstration knowledge base\"
  }")

echo "$KB_RESPONSE" | jq
KNOWLEDGE_BASE_ID=$(echo "$KB_RESPONSE" | jq -r '.id')
```

## 3. Upload the sample document

Run this command from the repository root:

```bash
DOCUMENT_RESPONSE=$(curl --silent --show-error \
  -X POST http://localhost:8000/documents/upload \
  -F "knowledge_base_id=$KNOWLEDGE_BASE_ID" \
  -F "file=@examples/sample_document.txt;type=text/plain")

echo "$DOCUMENT_RESPONSE" | jq
DOCUMENT_ID=$(echo "$DOCUMENT_RESPONSE" | jq -r '.id')
```

The upload response is HTTP `202` and initially reports `status: pending`.

## 4. Poll indexing status

```bash
curl --silent --show-error \
  "http://localhost:8000/documents/$DOCUMENT_ID" | jq
```

Repeat until `status` is `indexed`. A `failed` status includes an
`error_message`. LM Studio must have the configured embedding model loaded.

## 5. Run semantic search

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d "{
    \"knowledge_base_id\": \"$KNOWLEDGE_BASE_ID\",
    \"query\": \"Which databases does the platform use?\",
    \"limit\": 5
  }" | jq
```

The response contains ranked chunks, similarity scores, document IDs, and chunk
IDs. All results are filtered to the selected knowledge base.

## 6. Ask a grounded question

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -d "{
    \"knowledge_base_id\": \"$KNOWLEDGE_BASE_ID\",
    \"question\": \"What dependencies does the project use?\",
    \"limit\": 5
  }" | jq
```

The answer includes the retrieved source chunks used as evidence.

## 7. Stream a RAG answer

`curl -N` disables output buffering so SSE tokens appear as they are generated:

```bash
curl -N --silent --show-error \
  -X POST http://localhost:8000/qa/ask/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d "{
    \"knowledge_base_id\": \"$KNOWLEDGE_BASE_ID\",
    \"question\": \"Explain the document indexing lifecycle.\",
    \"limit\": 5
  }"
```

The final event is `data: [DONE]`.

## 8. Run the offline evaluation

The bundled evaluation case matches facts in the sample document:

```bash
python evaluation/run_eval.py \
  --knowledge-base-id "$KNOWLEDGE_BASE_ID"
```

Expected report fields:

```text
total_questions:  1
passed:           1
failed:           0
accuracy_percent: 100.00%
```

Model output is nondeterministic, so inspect failed keyword checks rather than
treating a single run as a complete quality assessment.
