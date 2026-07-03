"""Tests for the Langfuse observability gate (no-op safety is the contract)."""

import importlib
from unittest.mock import patch

import openai


def _reload_observability(env: dict[str, str]):
    with patch.dict("os.environ", env, clear=False):
        import app.observability as obs

        return importlib.reload(obs)


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


def test_enabled_with_keys() -> None:
    obs = _reload_observability(
        {
            "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
            "LANGFUSE_SECRET_KEY": "sk-lf-test",
            "LANGFUSE_HOST": "https://cloud.langfuse.com",
        }
    )
    assert obs.langfuse_enabled() is True
    assert obs.AsyncOpenAI is not openai.AsyncOpenAI
    assert obs.get_langfuse() is not None
    # Restore a disabled module for other tests.
    import app.observability as obs2

    importlib.reload(obs2)
