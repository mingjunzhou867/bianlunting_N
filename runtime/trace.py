"""Structured runtime tracing for review sessions.

Trace events are intentionally lightweight dictionaries so they can flow through
SSE, API payloads, and persisted snapshots without a schema migration.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, Iterator


_CURRENT_TRACE: ContextVar["TraceContext | None"] = ContextVar("current_trace", default=None)


def _utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, limit: int = 300) -> str:
    text = str(value or "")
    return text if len(text) <= limit else f"{text[:limit]}..."


class TraceContext:
    """Append-only structured trace for one debate session."""

    def __init__(self, session_id: str, id_card: str, policy_id: str):
        self.session_id = session_id
        self.id_card = id_card
        self.policy_id = policy_id
        self._events: list[dict[str, Any]] = []

    def add(
        self,
        stage: str,
        action: str,
        message: str,
        *,
        status: str = "info",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "event_id": f"trace_{len(self._events) + 1:04d}",
            "timestamp": _utc_iso(),
            "session_id": self.session_id,
            "policy_id": self.policy_id,
            "stage": stage,
            "action": action,
            "status": status,
            "log": _safe_text(message),
        }
        if payload:
            event["payload"] = payload
        self._events.append(event)
        return event

    def info(self, stage: str, action: str, message: str, **payload: Any) -> dict[str, Any]:
        return self.add(stage, action, message, status="info", payload=payload or None)

    def success(self, stage: str, action: str, message: str, **payload: Any) -> dict[str, Any]:
        return self.add(stage, action, message, status="success", payload=payload or None)

    def warning(self, stage: str, action: str, message: str, **payload: Any) -> dict[str, Any]:
        return self.add(stage, action, message, status="warning", payload=payload or None)

    def danger(self, stage: str, action: str, message: str, **payload: Any) -> dict[str, Any]:
        return self.add(stage, action, message, status="danger", payload=payload or None)

    def to_list(self) -> list[dict[str, Any]]:
        return [dict(event) for event in self._events]


def current_trace() -> TraceContext | None:
    return _CURRENT_TRACE.get()


@contextmanager
def use_trace(trace: TraceContext | None) -> Iterator[None]:
    token = _CURRENT_TRACE.set(trace)
    try:
        yield
    finally:
        _CURRENT_TRACE.reset(token)
