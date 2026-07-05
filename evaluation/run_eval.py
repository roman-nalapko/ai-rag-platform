#!/usr/bin/env python3
"""Run a lightweight offline evaluation against the local RAG API."""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_QUESTIONS_PATH = Path(__file__).with_name("test_questions.json")
PLACEHOLDER_KNOWLEDGE_BASE_ID = "optional-placeholder"


class EvaluationConfigurationError(ValueError):
    """Raised when the evaluation dataset or runtime options are invalid."""


class LocalAPIError(RuntimeError):
    """Raised when the local QA endpoint cannot return an answer."""


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    question: str
    expected_keywords: tuple[str, ...]
    knowledge_base_id: str | None


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    question: str
    passed: bool
    answer: str | None
    missing_keywords: tuple[str, ...]
    error: str | None = None


def load_cases(path: Path) -> list[EvaluationCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise EvaluationConfigurationError(
            f"Could not read evaluation dataset: {path}"
        ) from error
    except json.JSONDecodeError as error:
        raise EvaluationConfigurationError(
            f"Evaluation dataset contains invalid JSON: {error}"
        ) from error

    if not isinstance(payload, list) or not payload:
        raise EvaluationConfigurationError(
            "Evaluation dataset must be a non-empty JSON array"
        )

    return [parse_case(item, index) for index, item in enumerate(payload, start=1)]


def parse_case(item: Any, index: int) -> EvaluationCase:
    if not isinstance(item, dict):
        raise EvaluationConfigurationError(f"Question #{index} must be an object")

    question = item.get("question")
    keywords = item.get("expected_keywords")
    knowledge_base_id = item.get("knowledge_base_id")

    if not isinstance(question, str) or not question.strip():
        raise EvaluationConfigurationError(
            f"Question #{index} must contain non-empty 'question' text"
        )
    if (
        not isinstance(keywords, list)
        or not keywords
        or any(
            not isinstance(keyword, str) or not keyword.strip()
            for keyword in keywords
        )
    ):
        raise EvaluationConfigurationError(
            f"Question #{index} must contain non-empty 'expected_keywords'"
        )
    if knowledge_base_id is not None and not isinstance(knowledge_base_id, str):
        raise EvaluationConfigurationError(
            f"Question #{index} has an invalid 'knowledge_base_id'"
        )

    return EvaluationCase(
        question=question.strip(),
        expected_keywords=tuple(keyword.strip() for keyword in keywords),
        knowledge_base_id=knowledge_base_id,
    )


def call_qa(
    api_url: str,
    case: EvaluationCase,
    knowledge_base_id: str,
    limit: int,
    timeout: float,
) -> str:
    body = json.dumps(
        {
            "knowledge_base_id": knowledge_base_id,
            "question": case.question,
            "limit": limit,
        }
    ).encode("utf-8")
    request = Request(
        f"{api_url.rstrip('/')}/qa/ask",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LocalAPIError(f"HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise LocalAPIError(f"Local API is unavailable: {error.reason}") from error
    except TimeoutError as error:
        raise LocalAPIError("Local API request timed out") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LocalAPIError("Local API returned an invalid JSON response") from error

    answer = payload.get("answer") if isinstance(payload, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise LocalAPIError("Local API response does not contain a valid answer")
    return answer.strip()


def evaluate_case(
    case: EvaluationCase,
    api_url: str,
    fallback_knowledge_base_id: str | None,
    limit: int,
    timeout: float,
) -> EvaluationResult:
    knowledge_base_id = fallback_knowledge_base_id or case.knowledge_base_id
    if not knowledge_base_id or knowledge_base_id == PLACEHOLDER_KNOWLEDGE_BASE_ID:
        return EvaluationResult(
            question=case.question,
            passed=False,
            answer=None,
            missing_keywords=case.expected_keywords,
            error=(
                "knowledge_base_id is not configured; use --knowledge-base-id "
                "or EVAL_KNOWLEDGE_BASE_ID"
            ),
        )

    try:
        answer = call_qa(
            api_url=api_url,
            case=case,
            knowledge_base_id=knowledge_base_id,
            limit=limit,
            timeout=timeout,
        )
    except LocalAPIError as error:
        return EvaluationResult(
            question=case.question,
            passed=False,
            answer=None,
            missing_keywords=case.expected_keywords,
            error=str(error),
        )

    normalized_answer = answer.casefold()
    missing_keywords = tuple(
        keyword
        for keyword in case.expected_keywords
        if keyword.casefold() not in normalized_answer
    )
    return EvaluationResult(
        question=case.question,
        passed=not missing_keywords,
        answer=answer,
        missing_keywords=missing_keywords,
    )


def print_report(results: list[EvaluationResult], api_url: str) -> None:
    print("\nRAG Evaluation Report")
    print(f"API: {api_url.rstrip('/')}/qa/ask")
    print("=" * 72)

    for index, result in enumerate(results, start=1):
        label = "PASS" if result.passed else "FAIL"
        print(f"[{label}] {index}. {result.question}")
        if result.answer is not None:
            print(f"       Answer: {result.answer}")
        if result.missing_keywords:
            print(f"       Missing: {', '.join(result.missing_keywords)}")
        if result.error:
            print(f"       Error: {result.error}")

    total = len(results)
    passed = sum(result.passed for result in results)
    failed = total - passed
    accuracy = (passed / total * 100.0) if total else 0.0

    print("-" * 72)
    print(f"total_questions:  {total}")
    print(f"passed:           {passed}")
    print(f"failed:           {failed}")
    print(f"accuracy_percent: {accuracy:.2f}%")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the local RAG QA endpoint using keyword checks."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS_PATH,
        help="Path to the evaluation JSON dataset.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("EVAL_API_URL", "http://localhost:8000"),
        help="Local API base URL (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--knowledge-base-id",
        default=os.getenv("EVAL_KNOWLEDGE_BASE_ID"),
        help="Override knowledge_base_id for every evaluation question.",
    )
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 11))
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        print(
            "Configuration error: --timeout must be greater than zero",
            file=sys.stderr,
        )
        return 2

    try:
        cases = load_cases(args.questions)
    except EvaluationConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    results = [
        evaluate_case(
            case=case,
            api_url=args.api_url,
            fallback_knowledge_base_id=args.knowledge_base_id,
            limit=args.limit,
            timeout=args.timeout,
        )
        for case in cases
    ]
    print_report(results, args.api_url)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
