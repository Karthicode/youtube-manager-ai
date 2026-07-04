"""Tests that AgentService routes OpenAI + tool calls through the observability gate."""

import inspect
from unittest.mock import MagicMock, patch

from app.services import agent_service


def test_agent_service_uses_observability_client() -> None:
    src = inspect.getsource(agent_service)
    assert "from app.observability import" in src
    # The plain `from openai import AsyncOpenAI` import must be gone.
    assert "from openai import AsyncOpenAI" not in src


def test_execute_tool_records_span_with_cache_flag() -> None:
    service = agent_service.AgentService.__new__(agent_service.AgentService)
    service.user_id = 1
    service._redis = MagicMock()
    service._redis.get.return_value = '{"cached": true}'

    span = MagicMock()

    class FakeCtx:
        def __enter__(self):
            return span

        def __exit__(self, *args):
            return False

    with patch.object(agent_service, "tool_span", return_value=FakeCtx()) as ts:
        import asyncio

        result = asyncio.run(
            service._execute_tool("get_video_stats", {"metric": "overview"})
        )

    assert result == {"cached": True}
    ts.assert_called_once()
    assert ts.call_args.args[0] == "get_video_stats"
    span.update.assert_called()
    meta = span.update.call_args.kwargs.get("metadata") or {}
    assert meta.get("cache_hit") is True
