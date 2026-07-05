import logging
import uuid
from time import perf_counter

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import elapsed_ms, reset_request_id, set_request_id

logger = logging.getLogger("app.requests")


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
                logger.info(
                    "request_completed",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": elapsed_ms(started_at),
                        "outcome": "completed",
                    },
                )

        try:
            await self._app(scope, receive, send_with_request_id)
        except Exception:
            if not completed:
                logger.exception(
                    "request_failed",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": elapsed_ms(started_at),
                        "outcome": "failed",
                    },
                )
            raise
        finally:
            reset_request_id(token)
