# API Collection

This folder contains a Bruno collection for manually testing the local AI RAG
Platform API without copying curl commands from the documentation.

## Tool

Use [Bruno](https://www.usebruno.com/), an offline-friendly API client that
stores collections as plain text files.

## How to use

1. Start the local stack and API.
2. Open Bruno.
3. Import the collection folder:

   ```text
   docs/api-collection/AI-RAG-Platform
   ```

4. Select the `Local` environment.
5. Run requests in order.

## Environment variables

| Variable | Value |
| --- | --- |
| `base_url` | `http://localhost:8000` |
| `user_id` | Copy from `03 Create User` response |
| `access_token` | Copy from `04 Create Demo Token` response |
| `knowledge_base_id` | Copy from `05 Create Knowledge Base` response |
| `document_id` | Copy from `06 Upload Document` response |

## Notes

- The upload request references `examples/sample_document.txt`; run Bruno from
  the repository root or adjust the file path manually.
- No real secrets are stored in this collection. The `access_token`
  environment variable is a short-lived local demo JWT.
- LM Studio must be running for `/health/llm`, document indexing, semantic
  search, and QA requests.
