#!/usr/bin/env python3
"""Run the complete local AI RAG Platform demo flow."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_SAMPLE_FILE = ROOT / "examples" / "sample_document.txt"


class DemoError(RuntimeError):
    """Raised when the local demo flow cannot continue."""


@dataclass(frozen=True, slots=True)
class DemoConfig:
    api_url: str
    email: str
    sample_file: Path
    poll_interval_seconds: float
    poll_timeout_seconds: float
    request_timeout_seconds: float
    limit: int


def pretty(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    **kwargs: Any,
) -> dict[str, Any]:
    url = f"{str(client.base_url).rstrip('/')}{path}"
    try:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = error.response.text
        raise DemoError(
            f"{method} {url} failed with HTTP {error.response.status_code}: {detail}"
        ) from error
    except httpx.HTTPError as error:
        raise DemoError(f"{method} {url} failed: {error}") from error

    try:
        payload = response.json()
    except json.JSONDecodeError as error:
        raise DemoError(f"{method} {url} returned invalid JSON") from error

    if not isinstance(payload, dict):
        raise DemoError(f"{method} {url} returned unexpected JSON shape")
    return payload


def create_user(client: httpx.Client, email: str) -> dict[str, Any]:
    return request_json(
        client,
        "POST",
        "/users",
        json={"email": email},
    )


def create_demo_token(client: httpx.Client, user_id: str) -> dict[str, Any]:
    return request_json(
        client,
        "POST",
        "/auth/demo-token",
        json={"user_id": user_id},
    )


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def create_knowledge_base(
    client: httpx.Client,
    user_id: str,
    access_token: str,
) -> dict[str, Any]:
    return request_json(
        client,
        "POST",
        "/knowledge-bases",
        headers=auth_headers(access_token),
        json={
            "user_id": user_id,
            "name": "AI RAG Platform Demo",
            "description": "Automated portfolio demo knowledge base",
        },
    )


def upload_document(
    client: httpx.Client,
    knowledge_base_id: str,
    sample_file: Path,
    access_token: str,
) -> dict[str, Any]:
    if not sample_file.exists():
        raise DemoError(f"Sample document does not exist: {sample_file}")

    with sample_file.open("rb") as file_handle:
        return request_json(
            client,
            "POST",
            "/documents/upload",
            headers=auth_headers(access_token),
            data={"knowledge_base_id": knowledge_base_id},
            files={
                "file": (
                    sample_file.name,
                    file_handle,
                    "text/plain",
                )
            },
        )


def wait_for_indexing(
    client: httpx.Client,
    document_id: str,
    access_token: str,
    poll_interval_seconds: float,
    poll_timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + poll_timeout_seconds
    last_payload: dict[str, Any] | None = None

    while time.monotonic() < deadline:
        payload = request_json(
            client,
            "GET",
            f"/documents/{document_id}",
            headers=auth_headers(access_token),
        )
        last_payload = payload
        status = payload.get("status")
        chunks_count = payload.get("chunks_count")
        print(f"Indexing status: {status} | chunks_count={chunks_count}")

        if status == "indexed":
            return payload
        if status == "failed":
            raise DemoError(f"Document indexing failed: {payload.get('error_message')}")

        time.sleep(poll_interval_seconds)

    raise DemoError(
        "Timed out waiting for document indexing. "
        f"Last response: {pretty(last_payload)}"
    )


def semantic_search(
    client: httpx.Client,
    knowledge_base_id: str,
    access_token: str,
    limit: int,
) -> dict[str, Any]:
    return request_json(
        client,
        "POST",
        "/search",
        headers=auth_headers(access_token),
        json={
            "knowledge_base_id": knowledge_base_id,
            "query": "Which databases does the platform use?",
            "limit": limit,
        },
    )


def ask_question(
    client: httpx.Client,
    knowledge_base_id: str,
    access_token: str,
    limit: int,
) -> dict[str, Any]:
    return request_json(
        client,
        "POST",
        "/qa/ask",
        headers=auth_headers(access_token),
        json={
            "knowledge_base_id": knowledge_base_id,
            "question": "What dependencies does the project use?",
            "limit": limit,
        },
    )


def default_email() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"portfolio-demo+{timestamp}@example.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the complete local AI RAG Platform demo flow."
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Base URL for the local API. Default: {DEFAULT_API_URL}",
    )
    parser.add_argument(
        "--email",
        default=default_email(),
        help="Demo user email. Default: generated unique example.com address.",
    )
    parser.add_argument(
        "--sample-file",
        type=Path,
        default=DEFAULT_SAMPLE_FILE,
        help=f"Document to upload. Default: {DEFAULT_SAMPLE_FILE}",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between document status checks. Default: 2.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for indexing before failing. Default: 300.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=300.0,
        help="HTTP request timeout in seconds. Default: 300.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Top-K retrieval limit for search and QA. Default: 5.",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> DemoConfig:
    if args.limit < 1:
        raise DemoError("--limit must be greater than 0")
    if args.poll_interval <= 0:
        raise DemoError("--poll-interval must be greater than 0")
    if args.poll_timeout <= 0:
        raise DemoError("--poll-timeout must be greater than 0")
    if args.request_timeout <= 0:
        raise DemoError("--request-timeout must be greater than 0")

    return DemoConfig(
        api_url=args.api_url.rstrip("/"),
        email=args.email,
        sample_file=args.sample_file,
        poll_interval_seconds=args.poll_interval,
        poll_timeout_seconds=args.poll_timeout,
        request_timeout_seconds=args.request_timeout,
        limit=args.limit,
    )


def run_demo(config: DemoConfig) -> None:
    print("AI RAG Platform automated demo")
    print(f"API: {config.api_url}")
    print(f"Sample file: {config.sample_file}")
    print("=" * 72)

    with httpx.Client(
        base_url=config.api_url,
        timeout=config.request_timeout_seconds,
    ) as client:
        health = request_json(client, "GET", "/health")
        print("\n1. API health")
        print(pretty(health))

        print("\n2. Create user")
        user = create_user(client, config.email)
        user_id = str(user["id"])
        print(pretty(user))

        print("\n3. Create demo JWT")
        token = create_demo_token(client, user_id)
        access_token = str(token["access_token"])
        print(
            pretty(
                {"token_type": token["token_type"], "expires_in": token["expires_in"]}
            )
        )

        print("\n4. Create knowledge base")
        knowledge_base = create_knowledge_base(client, user_id, access_token)
        knowledge_base_id = str(knowledge_base["id"])
        print(pretty(knowledge_base))

        print("\n5. Upload sample document")
        document = upload_document(
            client,
            knowledge_base_id,
            config.sample_file,
            access_token,
        )
        document_id = str(document["id"])
        print(pretty(document))

        print("\n6. Poll indexing status")
        indexed_document = wait_for_indexing(
            client,
            document_id,
            access_token,
            config.poll_interval_seconds,
            config.poll_timeout_seconds,
        )
        print(pretty(indexed_document))

        print("\n7. Semantic search")
        search = semantic_search(client, knowledge_base_id, access_token, config.limit)
        print(pretty(search))

        print("\n8. RAG QA")
        qa = ask_question(client, knowledge_base_id, access_token, config.limit)
        print(pretty(qa))

        print("\nDemo completed")
        print("-" * 72)
        print(f"user_id={user_id}")
        print(f"knowledge_base_id={knowledge_base_id}")
        print(f"document_id={document_id}")


def main() -> int:
    try:
        config = build_config(parse_args())
        run_demo(config)
    except DemoError as error:
        print(f"Demo failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Demo interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
