import logging
import uuid
from time import perf_counter

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import elapsed_ms, reset_request_id, set_request_id
from app.core.metrics import metrics

logger = logging.getLogger("app.requests")


def _metrics_path(scope: Scope, raw_path: str) -> str:
    """Use the matched route template and collapse unmatched paths.

    Raw paths are attacker-controlled and would create unbounded Prometheus
    label cardinality if every unique 404 path became a separate time series.
    Starlette attaches the matched route to the scope before the response is
    sent, so parameterized routes retain a stable template such as
    ``/documents/{document_id}``.
    """
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    if raw_path in {"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}:
        return raw_path
    if raw_path == "/demo" or raw_path.startswith("/demo/"):
        return "/demo/{path}"
    return "/__unmatched__"


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        token = set_request_id(request_id)
        started_at = perf_counter()
        method = scope.get("method", "")
        path = scope.get("path", "")
        status_code = 500
        completed = False

        logger.info(
            "request_started",
            extra={"method": method, "path": path},
        )

        async def send_with_request_id(message: Message) -> None:
            nonlocal completed, status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    header
                    for header in message.get("headers", [])
                    if header[0].lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers

            await send(message)

            if (
                message["type"] == "http.response.body"
                and not message.get("more_body", False)
                and not completed
            ):
                completed = True
                duration_ms = elapsed_ms(started_at)
                duration_seconds = perf_counter() - started_at
                metrics_path = _metrics_path(scope, path)
                metrics.http_requests_total.inc(
                    method=method,
                    path=metrics_path,
                    status_code=str(status_code),
                )
                metrics.http_request_duration_seconds.observe(
                    duration_seconds,
                    method=method,
                    path=metrics_path,
                )
                logger.info(
                    "request_completed",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "outcome": "completed",
                    },
                )

        try:
            await self._app(scope, receive, send_with_request_id)
        except Exception:
            if not completed:
                duration_ms = elapsed_ms(started_at)
                duration_seconds = perf_counter() - started_at
                metrics_path = _metrics_path(scope, path)
                metrics.http_requests_total.inc(
                    method=method,
                    path=metrics_path,
                    status_code=str(status_code),
                )
                metrics.http_request_duration_seconds.observe(
                    duration_seconds,
                    method=method,
                    path=metrics_path,
                )
                logger.exception(
                    "request_failed",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "outcome": "failed",
                    },
                )
            raise
        finally:
            reset_request_id(token)
