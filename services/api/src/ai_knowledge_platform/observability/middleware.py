"""ASGI middleware that assigns request IDs and persists one trace record per request."""

import json
import logging
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ai_knowledge_platform.observability.tracing import Trace, active_trace, elapsed_ms

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

logger = logging.getLogger(__name__)


class TraceSink(Protocol):
    def write(self, record: dict[str, Any]) -> None: ...


class JsonlTraceSink:
    """Append each record as one JSON line to a daily file (UTC date of the request)."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._lock = Lock()

    def write(self, record: dict[str, Any]) -> None:
        day = str(record["started_at"])[:10]
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            with (self._directory / f"traces-{day}.jsonl").open("a", encoding="utf-8") as file:
                file.write(line)


class RequestTracingMiddleware:
    def __init__(self, app: ASGIApp, *, sink: TraceSink | None) -> None:
        self.app = app
        self.sink = sink

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace = Trace(request_id=_request_id(scope), method=scope["method"], path=scope["path"])
        # Unhandled exceptions never reach `http.response.start` here; the outer
        # server-error middleware answers 500, so that is the recorded default.
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = trace.request_id
            await send(message)

        started = time.perf_counter()
        try:
            with active_trace(trace):
                await self.app(scope, receive, send_with_request_id)
        finally:
            if self.sink is not None:
                record = trace.to_record(
                    route=_route_template(scope),
                    status_code=status_code,
                    duration_ms=elapsed_ms(started),
                )
                await _write_safely(self.sink, record)


async def _write_safely(sink: TraceSink, record: dict[str, Any]) -> None:
    """Tracing must never change the response the client already received."""
    try:
        await run_in_threadpool(sink.write, record)
    except Exception:
        logger.exception("Could not persist trace %s", record.get("request_id"))


def _request_id(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == b"x-request-id":
            candidate = bytes(value).decode("latin-1")
            if _SAFE_REQUEST_ID.fullmatch(candidate):
                return candidate
            break
    return uuid4().hex


def _route_template(scope: Scope) -> str:
    """Prefer `/documents/{document_id}` over a concrete path to keep records groupable."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    return str(scope.get("path", ""))
