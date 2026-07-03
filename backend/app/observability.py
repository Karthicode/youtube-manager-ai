"""Langfuse observability gate for the chat agent.

Tracing is a strict opt-in: when LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY are
unset, every export here is a no-op and the plain OpenAI client is used, so
dev/test environments and a keyless prod behave exactly as before. Tracing
failures must never break chat — helpers swallow and log Langfuse errors.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

from app.logger import api_logger


def langfuse_enabled() -> bool:
    """True when both Langfuse keys are present in the environment."""
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    )


if langfuse_enabled():
    # Importing langfuse.openai registers tracing on the OpenAI SDK as a
    # module-level side effect (register_tracing); the exported class is
    # openai.AsyncOpenAI itself — instrumentation lives in method patches.
    from langfuse import get_client
    from langfuse.openai import AsyncOpenAI  # noqa: F401
else:
    from openai import AsyncOpenAI  # noqa: F401

    get_client = None  # type: ignore[assignment]


def get_langfuse() -> Any | None:
    """Return the Langfuse client, or None when tracing is disabled."""
    if not langfuse_enabled() or get_client is None:
        return None
    try:
        return get_client()
    except Exception as e:  # pragma: no cover - defensive
        api_logger.warning(f"Langfuse client init failed: {e}")
        return None


class _NoOpSpan:
    """Span stand-in used when tracing is disabled or errors out."""

    def update(self, **kwargs: Any) -> None:
        return None


def _open_langfuse_span(
    name: str,
    as_type: str,
    input: Any,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> tuple[list[Any], Any]:
    """Best-effort span setup. Returns (open context managers, span).

    Never raises: on any Langfuse failure, returns ([], _NoOpSpan()).
    """
    client = get_langfuse()
    if client is None:
        return [], _NoOpSpan()
    opened: list[Any] = []
    try:
        span_cm = client.start_as_current_observation(
            as_type=as_type, name=name, input=input
        )
        span = span_cm.__enter__()
        opened.append(span_cm)
        if session_id is not None:
            from langfuse import propagate_attributes

            attrs_cm = propagate_attributes(
                session_id=session_id,
                user_id=user_id,
                metadata=metadata or {},
                tags=tags or [],
            )
            attrs_cm.__enter__()
            opened.append(attrs_cm)
        return opened, span
    except Exception as e:
        api_logger.warning(f"Langfuse span setup failed ({name}): {e}")
        _close_spans(opened)
        return [], _NoOpSpan()


def _close_spans(opened: list[Any]) -> None:
    """Close span context managers in reverse order; never raises."""
    for cm in reversed(opened):
        try:
            cm.__exit__(None, None, None)
        except Exception as e:  # pragma: no cover - defensive
            api_logger.warning(f"Langfuse span close failed: {e}")


@contextmanager
def trace_span(
    name: str,
    *,
    session_id: str,
    user_id: str,
    input: Any = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any]:
    """Root span for one chat turn, with session/user attribution.

    Yields a span-like object supporting .update(output=...). Caller-body
    exceptions propagate untouched; only Langfuse's own errors are swallowed.
    """
    opened, span = _open_langfuse_span(
        name,
        "span",
        input,
        session_id=session_id,
        user_id=user_id,
        metadata=metadata,
        tags=tags,
    )
    try:
        yield span
    finally:
        _close_spans(opened)


@contextmanager
def tool_span(name: str, *, input: Any = None) -> Iterator[Any]:
    """Span for a single agent tool execution. Same error contract as trace_span."""
    opened, span = _open_langfuse_span(name, "tool", input)
    try:
        yield span
    finally:
        _close_spans(opened)


def flush_langfuse() -> None:
    """Flush buffered spans; mandatory on serverless before the response ends."""
    client = get_langfuse()
    if client is None:
        return
    try:
        client.flush()
    except Exception as e:  # pragma: no cover - defensive
        api_logger.warning(f"Langfuse flush failed: {e}")
