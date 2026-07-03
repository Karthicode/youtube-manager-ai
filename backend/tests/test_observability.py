"""Tests for the Langfuse observability gate (no-op safety is the contract)."""

import importlib
import sys

import openai


def test_disabled_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    import app.observability as obs

    obs = importlib.reload(obs)
    assert obs.langfuse_enabled() is False
    assert obs.AsyncOpenAI is openai.AsyncOpenAI
    assert obs.get_langfuse() is None


def test_disabled_spans_are_noop_contexts(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    import app.observability as obs

    obs = importlib.reload(obs)
    with obs.trace_span("chat-turn", session_id="s1", user_id="1"):
        with obs.tool_span("filter_videos", input={"limit": 3}) as span:
            span.update(output={"ok": True}, metadata={"cache_hit": False})
    obs.flush_langfuse()  # must not raise


def test_caller_exceptions_propagate_through_spans(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    import app.observability as obs

    obs = importlib.reload(obs)
    import pytest

    with pytest.raises(ValueError, match="boom"):
        with obs.trace_span("chat-turn", session_id="s1", user_id="1"):
            raise ValueError("boom")
    with pytest.raises(ValueError, match="boom"):
        with obs.tool_span("filter_videos"):
            raise ValueError("boom")


def test_enabled_with_keys(monkeypatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    import app.observability as obs

    obs = importlib.reload(obs)
    assert obs.langfuse_enabled() is True
    # The drop-in re-exports openai.AsyncOpenAI; the instrumentation is the
    # import side effect — assert the patching module was actually imported.
    assert "langfuse.openai" in sys.modules
    assert obs.AsyncOpenAI is openai.AsyncOpenAI
    assert obs.get_langfuse() is not None

    # Restore a disabled module for other tests.
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    import app.observability as obs2

    importlib.reload(obs2)
