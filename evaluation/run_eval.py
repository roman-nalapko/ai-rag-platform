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
    expected_source_keywords: tuple[str, ...]
    expected_source_filenames: tuple[str, ...]
    knowledge_base_id: str | None


@dataclass(frozen=True, slots=True)
class EvaluationSource:
    filename: str | None
    content: str
    score: float | None


@dataclass(frozen=True, slots=True)
class QAResult:
    answer: str
    sources: tuple[EvaluationSource, ...]


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    question: str
    answer_passed: bool
    retrieval_passed: bool
    answer: str | None
    sources: tuple[EvaluationSource, ...]
    missing_keywords: tuple[str, ...]
    missing_source_keywords: tuple[str, ...]
    missing_source_filenames: tuple[str, ...]
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.answer_passed and self.retrieval_passed and self.error is None


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
    source_keywords = item.get("expected_source_keywords", [])
    source_filenames = item.get("expected_source_filenames", [])
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
    if not isinstance(source_keywords, list) or any(
        not isinstance(keyword, str) or not keyword.strip()
        for keyword in source_keywords
    ):
        raise EvaluationConfigurationError(
            f"Question #{index} has an invalid 'expected_source_keywords'"
        )
    if not isinstance(source_filenames, list) or any(
        not isinstance(filename, str) or not filename.strip()
        for filename in source_filenames
    ):
        raise EvaluationConfigurationError(
            f"Question #{index} has an invalid 'expected_source_filenames'"
        )

    return EvaluationCase(
        question=question.strip(),
        expected_keywords=tuple(keyword.strip() for keyword in keywords),
        expected_source_keywords=tuple(
            keyword.strip() for keyword in source_keywords
        ),
        expected_source_filenames=tuple(
            filename.strip() for filename in source_filenames
        ),
        knowledge_base_id=knowledge_base_id,
    )


def call_qa(
    api_url: str,
    case: EvaluationCase,
    knowledge_base_id: str,
    access_token: str | None,
    limit: int,
    timeout: float,
) -> QAResult:
    body = json.dumps(
        {
            "knowledge_base_id": knowledge_base_id,
            "question": case.question,
            "limit": limit,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    request = Request(
        f"{api_url.rstrip('/')}/qa/ask",
        data=body,
        headers=headers,
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
    raw_sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise LocalAPIError("Local API response does not contain a valid answer")
    if not isinstance(raw_sources, list):
        raise LocalAPIError("Local API response does not contain valid sources")

    sources = tuple(parse_source(source) for source in raw_sources)
    return QAResult(
        answer=answer.strip(),
        sources=sources,
    )


def parse_source(source: Any) -> EvaluationSource:
    if not isinstance(source, dict):
        raise LocalAPIError("Local API response contains an invalid source")

    filename = source.get("filename")
    content = source.get("content")
    score = source.get("score")

    if filename is not None and not isinstance(filename, str):
        raise LocalAPIError("Local API source contains an invalid filename")
    if not isinstance(content, str):
        raise LocalAPIError("Local API source contains invalid content")
    if score is not None and not isinstance(score, int | float):
        raise LocalAPIError("Local API source contains an invalid score")

    return EvaluationSource(
        filename=filename,
        content=content,
        score=float(score) if score is not None else None,
    )


def evaluate_case(
    case: EvaluationCase,
    api_url: str,
    fallback_knowledge_base_id: str | None,
    access_token: str | None,
    limit: int,
    timeout: float,
) -> EvaluationResult:
    knowledge_base_id = fallback_knowledge_base_id or case.knowledge_base_id
    if not knowledge_base_id or knowledge_base_id == PLACEHOLDER_KNOWLEDGE_BASE_ID:
        return EvaluationResult(
            question=case.question,
            answer_passed=False,
            retrieval_passed=False,
            answer=None,
            sources=(),
            missing_keywords=case.expected_keywords,
            missing_source_keywords=case.expected_source_keywords,
            missing_source_filenames=case.expected_source_filenames,
            error=(
                "knowledge_base_id is not configured; use --knowledge-base-id "
                "or EVAL_KNOWLEDGE_BASE_ID"
            ),
        )

    try:
        qa_result = call_qa(
            api_url=api_url,
            case=case,
            knowledge_base_id=knowledge_base_id,
            access_token=access_token,
            limit=limit,
            timeout=timeout,
        )
    except LocalAPIError as error:
        return EvaluationResult(
            question=case.question,
            answer_passed=False,
            retrieval_passed=False,
            answer=None,
            sources=(),
            missing_keywords=case.expected_keywords,
            missing_source_keywords=case.expected_source_keywords,
            missing_source_filenames=case.expected_source_filenames,
            error=str(error),
        )

    normalized_answer = qa_result.answer.casefold()
    missing_keywords = tuple(
        keyword
        for keyword in case.expected_keywords
        if keyword.casefold() not in normalized_answer
    )
    combined_source_content = "\n".join(
        source.content for source in qa_result.sources
    ).casefold()
    source_filenames = {
        source.filename.casefold()
        for source in qa_result.sources
        if source.filename is not None
    }
    missing_source_keywords = tuple(
        keyword
        for keyword in case.expected_source_keywords
        if keyword.casefold() not in combined_source_content
    )
    missing_source_filenames = tuple(
        filename
        for filename in case.expected_source_filenames
        if filename.casefold() not in source_filenames
    )
    return EvaluationResult(
        question=case.question,
        answer_passed=not missing_keywords,
        retrieval_passed=not missing_source_keywords
        and not missing_source_filenames,
        answer=qa_result.answer,
        sources=qa_result.sources,
        missing_keywords=missing_keywords,
        missing_source_keywords=missing_source_keywords,
        missing_source_filenames=missing_source_filenames,
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
        print(f"       Answer keywords: {'PASS' if result.answer_passed else 'FAIL'}")
        print(f"       Retrieval:       {'PASS' if result.retrieval_passed else 'FAIL'}")
        if result.sources:
            print(f"       Sources:         {len(result.sources)}")
        if result.missing_keywords:
            print(f"       Missing: {', '.join(result.missing_keywords)}")
        if result.missing_source_keywords:
            print(
                "       Missing source keywords: "
                f"{', '.join(result.missing_source_keywords)}"
            )
        if result.missing_source_filenames:
            print(
                "       Missing source filenames: "
                f"{', '.join(result.missing_source_filenames)}"
            )
        if result.error:
            print(f"       Error: {result.error}")

    total = len(results)
    passed = sum(result.passed for result in results)
    failed = total - passed
    accuracy = (passed / total * 100.0) if total else 0.0
    answer_passed = sum(result.answer_passed and result.error is None for result in results)
    retrieval_passed = sum(
        result.retrieval_passed and result.error is None for result in results
    )
    answer_accuracy = (answer_passed / total * 100.0) if total else 0.0
    retrieval_hit_rate = (retrieval_passed / total * 100.0) if total else 0.0

    print("-" * 72)
    print(f"total_questions:  {total}")
    print(f"passed:           {passed}")
    print(f"failed:           {failed}")
    print(f"accuracy_percent: {accuracy:.2f}%")
    print(f"answer_accuracy_percent: {answer_accuracy:.2f}%")
    print(f"retrieval_hit_rate_percent: {retrieval_hit_rate:.2f}%")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the local RAG QA endpoint.\n\n"
            "Modes:\n"
            "  keyword   (default) Check that expected keywords appear in the answer.\n"
            "  llm-judge Send each answer to the LLM and ask it to score faithfulness 0-10."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    parser.add_argument(
        "--access-token",
        default=os.getenv("EVAL_ACCESS_TOKEN"),
        help="Bearer token for protected QA requests.",
    )
    parser.add_argument(
        "--mode",
        choices=["keyword", "llm-judge"],
        default=os.getenv("EVAL_MODE", "keyword"),
        help="Evaluation mode: 'keyword' (default) or 'llm-judge'.",
    )
    parser.add_argument(
        "--llm-url",
        default=os.getenv("EVAL_LLM_URL", "http://localhost:1234/v1"),
        help="OpenAI-compatible LLM base URL used by llm-judge mode.",
    )
    parser.add_argument(
        "--llm-model",
        default=os.getenv("EVAL_LLM_MODEL", ""),
        help="Chat model name for llm-judge mode (passed as model field).",
    )
    parser.add_argument(
        "--llm-min-score",
        type=float,
        default=float(os.getenv("EVAL_LLM_MIN_SCORE", "6.0")),
        help="Minimum LLM judge score (0-10) to consider a case passing (default: 6.0).",
    )
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 11))
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser.parse_args()




# ── LLM-as-judge ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LLMJudgeResult:
    question: str
    answer: str
    score: float  # 0-10
    reasoning: str
    passed: bool
    error: str | None = None


def _llm_chat(
    llm_url: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: float,
) -> str:
    """Call an OpenAI-compatible /chat/completions endpoint. Returns assistant content."""
    url = llm_url.rstrip("/") + "/chat/completions"
    body = json.dumps({"model": model or "local-model", "messages": messages, "max_tokens": 256}).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except (HTTPError, URLError) as error:
        raise LocalAPIError(f"LLM judge request failed: {error}") from error
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as error:
        raise LocalAPIError("Unexpected LLM judge response format") from error


def judge_with_llm(
    case: EvaluationCase,
    qa_result: QAResult,
    llm_url: str,
    model: str,
    min_score: float,
    timeout: float,
) -> LLMJudgeResult:
    """Ask the LLM to score faithfulness and relevance of the answer."""
    sources_text = "\n\n".join(
        f"[Source {i+1}]: {s.content[:500]}" for i, s in enumerate(qa_result.sources)
    )
    prompt = (
        f"You are an objective RAG evaluator. Given a question, retrieved context, and an answer, "
        f"score the answer on faithfulness and relevance from 0 to 10.\n\n"
        f"Question: {case.question}\n\n"
        f"Retrieved Context:\n{sources_text or '(no sources retrieved)'}\n\n"
        f"Answer: {qa_result.answer}\n\n"
        f"Respond with ONLY:\nSCORE: <integer 0-10>\nREASON: <one sentence>"
    )
    try:
        content = _llm_chat(
            llm_url=llm_url,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
    except LocalAPIError as error:
        return LLMJudgeResult(
            question=case.question,
            answer=qa_result.answer,
            score=0.0,
            reasoning="",
            passed=False,
            error=str(error),
        )

    # Parse SCORE: N
    score = 0.0
    reasoning = content
    for line in content.splitlines():
        if line.upper().startswith("SCORE:"):
            try:
                score = float(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.upper().startswith("REASON:"):
            reasoning = line.split(":", 1)[1].strip()

    return LLMJudgeResult(
        question=case.question,
        answer=qa_result.answer,
        score=score,
        reasoning=reasoning,
        passed=score >= min_score,
    )


def print_llm_judge_report(results: list[LLMJudgeResult], api_url: str, min_score: float) -> None:
    print("\nRAG LLM-Judge Evaluation Report")
    print(f"API: {api_url.rstrip('/')}/qa/ask  |  min_score: {min_score}")
    print("=" * 72)
    for i, result in enumerate(results, 1):
        label = "PASS" if result.passed else "FAIL"
        print(f"[{label}] {i}. {result.question}")
        print(f"       Score:   {result.score:.1f}/10")
        if result.reasoning:
            print(f"       Reason:  {result.reasoning}")
        if result.error:
            print(f"       Error:   {result.error}")
    print("-" * 72)
    total = len(results)
    passed = sum(r.passed for r in results)
    avg_score = sum(r.score for r in results) / total if total else 0.0
    print(f"total_questions: {total}")
    print(f"passed:          {passed}")
    print(f"failed:          {total - passed}")
    print(f"avg_llm_score:   {avg_score:.2f}/10")
    print(f"pass_rate:       {passed / total * 100:.2f}%")


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

    if args.mode == "llm-judge":
        # Run QA for each case, then judge with LLM
        judge_results: list[LLMJudgeResult] = []
        for case in cases:
            kb_id = args.knowledge_base_id or case.knowledge_base_id
            if not kb_id or kb_id == PLACEHOLDER_KNOWLEDGE_BASE_ID:
                judge_results.append(LLMJudgeResult(
                    question=case.question,
                    answer="",
                    score=0.0,
                    reasoning="",
                    passed=False,
                    error="knowledge_base_id not configured; use --knowledge-base-id",
                ))
                continue
            try:
                qa_result = call_qa(
                    api_url=args.api_url,
                    case=case,
                    knowledge_base_id=kb_id,
                    access_token=args.access_token,
                    limit=args.limit,
                    timeout=args.timeout,
                )
            except LocalAPIError as error:
                judge_results.append(LLMJudgeResult(
                    question=case.question,
                    answer="",
                    score=0.0,
                    reasoning="",
                    passed=False,
                    error=str(error),
                ))
                continue
            judge_results.append(judge_with_llm(
                case=case,
                qa_result=qa_result,
                llm_url=args.llm_url,
                model=args.llm_model,
                min_score=args.llm_min_score,
                timeout=args.timeout,
            ))
        print_llm_judge_report(judge_results, args.api_url, args.llm_min_score)
        return 0 if all(r.passed for r in judge_results) else 1

    # Default: keyword mode
    results = [
        evaluate_case(
            case=case,
            api_url=args.api_url,
            fallback_knowledge_base_id=args.knowledge_base_id,
            access_token=args.access_token,
            limit=args.limit,
            timeout=args.timeout,
        )
        for case in cases
    ]
    print_report(results, args.api_url)
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

