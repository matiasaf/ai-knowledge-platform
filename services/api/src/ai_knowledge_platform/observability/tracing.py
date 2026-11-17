"""Request-scoped traces and stage spans (ADR 6). Standard library only.

The active trace is held in a context variable, so services and adapters can open
spans without receiving a tracer argument. Outside a traced request, `span()` is a
no-op that still yields a usable handle.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

AttributeValue = str | int | float | bool | None | list[str] | list[int]

TRACE_SCHEMA_VERSION = 1


@dataclass(slots=True)
class Span:
    name: str
    started_at: datetime
    attributes: dict[str, AttributeValue] = field(default_factory=dict)
    duration_ms: float | None = None
    status: str = "ok"
    error: str | None = None

    def set(self, key: str, value: AttributeValue) -> None:
        self.attributes[key] = value

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "started_at": self.started_at.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "attributes": dict(self.attributes),
        }


@dataclass(slots=True)
class Trace:
    request_id: str
    method: str
    path: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attributes: dict[str, AttributeValue] = field(default_factory=dict)
    spans: list[Span] = field(default_factory=list)

    def to_record(self, *, route: str, status_code: int, duration_ms: float) -> dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "request_id": self.request_id,
            "method": self.method,
            "route": route,
            "status_code": status_code,
            "started_at": self.started_at.isoformat(),
            "duration_ms": duration_ms,
            "attributes": dict(self.attributes),
            "spans": [span.to_record() for span in self.spans],
        }


_current_trace: ContextVar[Trace | None] = ContextVar("akp_current_trace", default=None)


def current_trace() -> Trace | None:
    return _current_trace.get()


@contextmanager
def active_trace(trace: Trace) -> Iterator[Trace]:
    """Make `trace` the current trace for the enclosed code."""
    token = _current_trace.set(trace)
    try:
        yield trace
    finally:
        _current_trace.reset(token)


def set_trace_attribute(key: str, value: AttributeValue) -> None:
    trace = _current_trace.get()
    if trace is not None:
        trace.attributes[key] = value


@contextmanager
def span(name: str, **attributes: AttributeValue) -> Iterator[Span]:
    """Time one stage. Exceptions mark the span as failed and propagate unchanged."""
    current = Span(name=name, started_at=datetime.now(UTC), attributes=dict(attributes))
    started = time.perf_counter()
    try:
        yield current
    except BaseException as exc:
        current.status = "error"
        current.error = type(exc).__name__
        raise
    finally:
        current.duration_ms = elapsed_ms(started)
        trace = _current_trace.get()
        if trace is not None:
            trace.spans.append(current)


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
