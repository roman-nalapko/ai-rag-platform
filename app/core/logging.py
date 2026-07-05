import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)

LOG_EXTRA_FIELDS = (
    "method",
    "path",
    "status_code",
    "duration_ms",
    "operation",
    "outcome",
    "document_id",
    "knowledge_base_id",
    "chunks_count",
    "embedding_dimensions",
    "result_count",
    "limit",
)


class JSONFormatter(logging.Formatter):
    """Serialize application log records without request bodies or headers."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for field in LOG_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        # Exception messages may contain provider responses. Record only the
        # exception type so secrets, prompts, and document text cannot leak.
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Uvicorn installs text handlers before importing the application. Route
    # its records through the same JSON formatter to keep stdout consistent.
    for logger_name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(log_level)

    # The middleware provides safer access logs without query strings. Disable
    # Uvicorn's duplicate request line, which may include sensitive query data.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
    access_logger.disabled = True

    # Provider libraries are wrapped by application-level operational events.
    # Keep their verbose HTTP internals out of normal JSON output.
    for logger_name in ("httpx", "httpcore", "openai"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    logging.captureWarnings(True)


def set_request_id(request_id: str) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)


def elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)
