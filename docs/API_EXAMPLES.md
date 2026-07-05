# API Examples

The examples assume that FastAPI is running on `localhost:8000`, LM Studio on
`localhost:1234`, and Qdrant on `localhost:6333`.

## API health

```bash
curl --silent --show-error http://localhost:8000/health
```

Expected response:

```json
{
  "status": "running",
  "mode": "local-ai"
}
```

## LM Studio health

This request generates an embedding for `health check`. The reported dimension
comes from the model response and is not hardcoded.

```bash
curl --silent --show-error http://localhost:8000/health/llm
```

Example response:

```json
{
  "status": "ok",
  "provider": "lm-studio",
  "embedding_dimensions": 768
}
```

## Create a user

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"email":"engineer@example.com"}'
```

Example response:

```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "email": "engineer@example.com",
  "created_at": "2026-07-04T17:00:00Z"
}
```

Duplicate normalized emails return HTTP `409`.

## Create a knowledge base

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/knowledge-bases \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"11111111-1111-1111-1111-111111111111",
    "name":"Engineering Docs",
    "description":"Backend and AI documentation"
  }'
```

Example response:

```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "user_id": "11111111-1111-1111-1111-111111111111",
  "name": "Engineering Docs",
  "description": "Backend and AI documentation",
  "created_at": "2026-07-04T17:01:00Z"
}
```

## List a user's knowledge bases

```bash
curl --silent --show-error \
  "http://localhost:8000/knowledge-bases?user_id=11111111-1111-1111-1111-111111111111"
```

The response is an array of knowledge bases owned by that user. Unknown users
return HTTP `404`.

## Upload a document

Upload a UTF-8 TXT file:

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/documents/upload \
  -F "knowledge_base_id=22222222-2222-2222-2222-222222222222" \
  -F "file=@document.txt;type=text/plain"
```

Upload a PDF file:

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/documents/upload \
  -F "knowledge_base_id=22222222-2222-2222-2222-222222222222" \
  -F "file=@document.pdf;type=application/pdf"
```

Example response:

```json
{
  "id": "f914fdc8-ad6c-4c55-afc6-1039a82ff580",
  "knowledge_base_id": "22222222-2222-2222-2222-222222222222",
  "filename": "document.txt",
  "content_type": "text/plain",
  "created_at": "2026-07-05T10:00:00Z",
  "processed": false,
  "status": "pending",
  "error_message": null,
  "chunks_count": 0,
  "indexed": false
}
```

The endpoint returns HTTP `202` after metadata and the raw file are persisted.
Extraction, chunking, embedding, and Qdrant indexing continue in a FastAPI
background task. Supported file types are `.txt` with `text/plain` and `.pdf`
with `application/pdf`. The knowledge base must already exist.

## Check document processing status

```bash
curl --silent --show-error \
  http://localhost:8000/documents/f914fdc8-ad6c-4c55-afc6-1039a82ff580
```

Successful processing:

```json
{
  "id": "f914fdc8-ad6c-4c55-afc6-1039a82ff580",
  "knowledge_base_id": "22222222-2222-2222-2222-222222222222",
  "filename": "document.txt",
  "content_type": "text/plain",
  "created_at": "2026-07-05T10:00:00Z",
  "processed": true,
  "status": "indexed",
  "error_message": null,
  "chunks_count": 3
}
```

For failed processing, `status` is `failed`, `processed` remains `false`, and
`error_message` contains a safe failure description. Search and QA can retrieve
the document only after its vectors reach Qdrant and the status becomes
`indexed`.

## Semantic search

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "22222222-2222-2222-2222-222222222222",
    "query": "Which Python dependencies are used?",
    "limit": 5
  }'
```

Example response:

```json
{
  "query": "Which Python dependencies are used?",
  "results": [
    {
      "document_id": "f914fdc8-ad6c-4c55-afc6-1039a82ff580",
      "chunk_id": "065bc430-9784-48a1-bd1d-6fc21fc0ec1d",
      "chunk_index": 0,
      "filename": "requirements.txt",
      "content": "fastapi>=0.125.0...",
      "score": 0.87
    }
  ]
}
```

`limit` defaults to `5` and accepts values from `1` to `50`.

`knowledge_base_id` is required. Qdrant applies it as a payload filter, so
results cannot contain chunks from another knowledge base. Unknown knowledge
bases return HTTP `404`.

## RAG question answering

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id": "22222222-2222-2222-2222-222222222222",
    "question": "Which Python dependencies are used?",
    "limit": 5
  }'
```

Example response:

```json
{
  "question": "Which Python dependencies are used?",
  "answer": "The project uses FastAPI, SQLAlchemy, asyncpg, the Qdrant client, the OpenAI SDK, and pypdf.",
  "sources": [
    {
      "document_id": "f914fdc8-ad6c-4c55-afc6-1039a82ff580",
      "chunk_id": "065bc430-9784-48a1-bd1d-6fc21fc0ec1d",
      "filename": "requirements.txt",
      "chunk_index": 0,
      "score": 0.87,
      "content": "fastapi>=0.125.0..."
    }
  ]
}
```

If the retrieved context does not contain the answer, the service instructs
the model to return:

```text
I don't have enough information in the provided documents.
```

`limit` defaults to `5` and accepts values from `1` to `10` to keep the local
chat context bounded.

## Create a conversation

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "title":"Dependency questions"
  }'
```

Example response:

```json
{
  "id": "33333333-3333-3333-3333-333333333333",
  "knowledge_base_id": "22222222-2222-2222-2222-222222222222",
  "title": "Dependency questions",
  "created_at": "2026-07-04T18:00:00Z"
}
```

The title is optional. An unknown knowledge base returns HTTP `404`.

## Continue a RAG conversation

Pass `conversation_id` to `/qa/ask` to include the last five stored messages in
the prompt and persist the new user/assistant exchange:

```bash
curl --silent --show-error \
  -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "conversation_id":"33333333-3333-3333-3333-333333333333",
    "question":"Which of those dependencies handles vector search?",
    "limit":5
  }'
```

The conversation must belong to the requested knowledge base. A missing or
out-of-scope conversation returns HTTP `404`. Omit `conversation_id` to use
stateless QA.

## Stream a RAG answer

Use `curl -N` to disable output buffering and display tokens as they arrive:

```bash
curl -N --silent --show-error \
  -X POST http://localhost:8000/qa/ask/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "knowledge_base_id":"22222222-2222-2222-2222-222222222222",
    "conversation_id":"33333333-3333-3333-3333-333333333333",
    "question":"Which dependency handles vector search?",
    "limit":5
  }'
```

Example SSE response:

```text
data: Qdrant

data:  handles vector search.

data: [DONE]

```

The endpoint reuses the normal QA request. It validates the knowledge base and
conversation, performs retrieval, and opens the LM Studio stream before the SSE
response begins. After normal completion, the complete user/assistant exchange
is saved. If the client disconnects or generation fails mid-stream, a partial
assistant message is not persisted.

## Read conversation history

```bash
curl --silent --show-error \
  http://localhost:8000/conversations/33333333-3333-3333-3333-333333333333/messages
```

Example response:

```json
[
  {
    "id": "44444444-4444-4444-4444-444444444444",
    "conversation_id": "33333333-3333-3333-3333-333333333333",
    "role": "user",
    "content": "Which Python dependencies are used?",
    "created_at": "2026-07-04T18:01:00Z"
  },
  {
    "id": "55555555-5555-5555-5555-555555555555",
    "conversation_id": "33333333-3333-3333-3333-333333333333",
    "role": "assistant",
    "content": "The project uses FastAPI, SQLAlchemy, asyncpg, and Qdrant.",
    "created_at": "2026-07-04T18:01:01Z"
  }
]
```

## Common errors

| Status | Meaning |
| --- | --- |
| `400` | Invalid upload filename |
| `404` | Referenced user, knowledge base, or conversation does not exist |
| `409` | A user with the same normalized email already exists |
| `415` | Unsupported upload extension or media type |
| `422` | Request validation failure |
| `500` | Qdrant indexing/search failure or unexpected server error |
| `503` | LM Studio is unavailable or cannot run the configured model |

## Inspect Qdrant data

Open [http://localhost:6333/dashboard](http://localhost:6333/dashboard), select
`Collections`, and open `document_chunks`. To inspect payloads without vectors:

```bash
curl --silent --show-error \
  -X POST http://localhost:6333/collections/document_chunks/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit":10,"with_payload":true,"with_vector":false}'
```
