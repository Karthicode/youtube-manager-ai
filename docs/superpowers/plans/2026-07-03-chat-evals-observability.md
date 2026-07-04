# Chat Observability + Eval Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trace every chat-agent turn in Langfuse (model calls, tool calls + results, cache hits, errors) and build a golden-dataset eval pipeline with deterministic scorers, per the spec at `docs/superpowers/specs/2026-07-03-chat-evals-observability-design.md`.

**Architecture:** A single gate module (`app/observability.py`) makes Langfuse a strict opt-in: when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are unset everything no-ops and the plain OpenAI client is used. `AgentService.chat()` wraps each turn in a Langfuse span with `propagate_attributes(session_id, user_id)`; the OpenAI drop-in captures every Responses-API call as a generation; `_execute_tool` gets an explicit tool span. Evals live in `backend/evals/`: a seeded pgvector DB, YAML dataset, pure-function scorers, and a runner that uploads results to Langfuse via `run_experiment`.

**Tech Stack:** Langfuse Python SDK v3+ (OTel-based), `langfuse.openai` drop-in (Responses API supported since 2025-03), Postgres+pgvector via docker compose, pytest, PyYAML (already a transitive dep — verify import works, else add).

## Global Constraints

- **No-op requirement (spec):** with Langfuse env vars unset, behavior and imports must be identical to today — chat must never break because of tracing. All Langfuse calls wrapped so exporter errors log a warning and continue.
- **Env var names:** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (already in `backend/.env`, git-ignored). `Settings` has `extra="ignore"` (`backend/app/config.py:8`) so no config.py changes are needed.
- **Serverless flush (spec):** `flush()` must run in a `finally` at the end of the chat request on Vercel.
- **Dependency rule (CRITICAL, deployment memory):** every `poetry add` must be immediately mirrored in `backend/requirements.txt` with the locked version from `poetry show <pkg>` — Vercel installs from requirements.txt, not poetry.lock.
- **Backend quality gate after every task:** `cd backend && poetry run black . && poetry run ruff check . && poetry run mypy . && poetry run pytest` — all pass.
- **Commit messages** end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`. NEVER `git push` without user approval.
- **Docs-first (langfuse skill):** if any Langfuse API call in this plan errors unexpectedly, fetch current docs (`curl -s https://langfuse.com/api/search-docs?query=...`) before improvising.
- **Trace naming (spec):** trace name `chat-turn`, tags include `prompt_version` (current value: `"v2"` — the post-freshness-fix prompt).

---

### Task 1: Observability gate module + langfuse dependency

**Files:**
- Create: `backend/app/observability.py`
- Test: `backend/tests/test_observability.py`
- Modify: `backend/pyproject.toml` + `backend/requirements.txt` (via commands)

**Interfaces:**
- Produces (used by Tasks 2 and 5):
  - `observability.langfuse_enabled() -> bool`
  - `observability.AsyncOpenAI` — the wrapped class when enabled, plain `openai.AsyncOpenAI` otherwise
  - `observability.get_langfuse()` — Langfuse client or `None`
  - `observability.flush_langfuse() -> None` — safe always
  - `observability.trace_span(name, *, session_id, user_id, input=None, metadata=None, tags=None)` — context manager; no-op `nullcontext` when disabled
  - `observability.tool_span(name, *, input=None)` — context manager yielding a span-like object with `.update(**kwargs)` (no-op object when disabled)

- [ ] **Step 1: Add the dependency**

```bash
cd backend && poetry add langfuse
poetry show langfuse | head -3   # note the locked version, e.g. 3.x.y
```

Append to `backend/requirements.txt` (exact locked version from the previous command):

```
langfuse==<locked-version>
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_observability.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && poetry run pytest tests/test_observability.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.observability'`

- [ ] **Step 4: Implement `backend/app/observability.py`**

```python
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
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )


if langfuse_enabled():
    # The drop-in wrapper auto-traces every OpenAI call (incl. Responses API)
    # as a Langfuse generation with model, tokens, cost, and latency.
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
```

Error contract: Langfuse setup/close failures are swallowed (logged warnings);
caller-body exceptions ALWAYS propagate — `test_caller_exceptions_propagate_through_spans`
pins this behavior.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && poetry run pytest tests/test_observability.py -v`
Expected: 4 passed.

**Known caveat to verify while running:** with keys set (`test_enabled_with_keys`), the SDK may log a warning about unreachable host at flush time — that's fine; the test must not flush. If the langfuse import itself needs network at init, wrap init in the existing try/except (it does not, per docs — init is lazy).

- [ ] **Step 6: Quality gate**

Run: `cd backend && poetry run black . && poetry run ruff check . && poetry run mypy . && poetry run pytest`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/observability.py backend/tests/test_observability.py backend/pyproject.toml backend/poetry.lock backend/requirements.txt
git commit -m "feat: add Langfuse observability gate module

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Instrument AgentService + flush in chat router

**Files:**
- Modify: `backend/app/services/agent_service.py` (client import ~line 12+197, `chat()` ~line 675, `_execute_tool` ~line 282)
- Modify: `backend/app/routers/chat.py` (the `event_stream` generator inside `send_message`, ~line 104)
- Test: `backend/tests/test_agent_tracing.py` (new)

**Interfaces:**
- Consumes: Task 1's `observability.AsyncOpenAI`, `trace_span`, `tool_span`, `flush_langfuse`.
- Produces: traced chat turns named `chat-turn` with tags `["chat", "prompt:v2"]`; tool spans named after the tool with `cache_hit` metadata. No signature changes anywhere.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent_tracing.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest tests/test_agent_tracing.py -v`
Expected: FAIL — no `from app.observability import` in source / `tool_span` attribute missing.

- [ ] **Step 3: Implement in `agent_service.py`**

1. Replace the OpenAI import (line 12) and add gate imports:

```python
# remove:
from openai import AsyncOpenAI
# add:
from app.observability import AsyncOpenAI, tool_span, trace_span
```

(`AgentService.__init__` line 197 needs no change — `AsyncOpenAI(api_key=...)` now resolves to the wrapped class when enabled.)

2. Wrap the whole `_execute_tool` body in a tool span. The method currently starts with the `cacheable` check; restructure to:

```python
    async def _execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Execute a tool call and return the result. [keep existing docstring body]"""
        with tool_span(tool_name, input=arguments) as span:
            result, cache_hit = await self._execute_tool_inner(tool_name, arguments)
            span.update(
                output=result,
                metadata={"cache_hit": cache_hit, "user_id": self.user_id},
            )
            return result

    async def _execute_tool_inner(
        self, tool_name: str, arguments: dict
    ) -> tuple[Any, bool]:
        """Original tool dispatch; returns (result, served_from_cache)."""
```

Move the existing body into `_execute_tool_inner` with two mechanical edits:
- the cache-hit early return becomes `return json.loads(cached_raw), True`
- every other `return result`-style exit returns `(result, False)`; the unknown-tool and exception paths return `({"error": ...}, False)`.

3. Wrap the chat turn in `chat()` (line 675). Immediately after the docstring, wrap the ENTIRE existing body:

```python
        with trace_span(
            "chat-turn",
            session_id=session_id,
            user_id=str(self.user_id),
            input=message,
            tags=["chat", "prompt:v2"],
        ) as turn_span:
            ... entire existing body, indented one level ...
```

and right after `final_text = "\n".join(text_parts)` add:

```python
            turn_span.update(output=final_text)
```

(The generator yields while the span is open — that is fine: the span closes when the generator completes, capturing full turn latency.)

- [ ] **Step 4: Flush in `backend/app/routers/chat.py`**

In `send_message`'s `event_stream` generator, wrap the existing body in `try/finally`:

```python
from app.observability import flush_langfuse

    async def event_stream():
        try:
            ... existing body unchanged ...
        finally:
            # Serverless: force-send buffered spans before Vercel freezes us.
            flush_langfuse()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && poetry run pytest tests/test_agent_tracing.py tests/test_agent_service.py -v`
Expected: all pass (freshness tests from the chat-fix must not regress).

- [ ] **Step 6: Quality gate**

Run: `cd backend && poetry run black . && poetry run ruff check . && poetry run mypy . && poetry run pytest`
Expected: all pass.

- [ ] **Step 7: Live smoke test (only if local backend is runnable; otherwise defer to final task)**

With `backend/.env` containing the real keys: start the backend, send one chat message, then check https://cloud.langfuse.com → Traces for a `chat-turn` trace with nested generation + tool spans. If the local backend can't run (no local DB), note this as deferred to post-deploy verification.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/agent_service.py backend/app/routers/chat.py backend/tests/test_agent_tracing.py
git commit -m "feat: trace chat turns, generations, and tool calls in Langfuse

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Eval infrastructure — docker DB, seed script, dataset

**Files:**
- Create: `backend/docker-compose.evals.yml`
- Create: `backend/evals/__init__.py` (empty)
- Create: `backend/evals/db.py`
- Create: `backend/evals/seed.py`
- Create: `backend/evals/dataset.yaml`
- Test: `backend/tests/test_evals_dataset.py`

**Interfaces:**
- Produces (for Task 5): `evals.db.get_eval_session() -> Session` (SQLAlchemy session bound to `EVALS_DATABASE_URL`, default `postgresql://evals:evals@localhost:55432/evals`); `evals.seed.EVAL_USER_EMAIL = "eval@example.com"`; `evals.seed.seed(db) -> int` (returns eval user id, idempotent); dataset cases with keys `id, message, expected_tools, expected_titles_any, forbid_tools, expect_freshness_caveat`.

- [ ] **Step 1: `backend/docker-compose.evals.yml`**

```yaml
services:
  evals-db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: evals
      POSTGRES_PASSWORD: evals
      POSTGRES_DB: evals
    ports:
      - "55432:5432"
```

- [ ] **Step 2: `backend/evals/db.py`**

```python
"""SQLAlchemy session factory for the isolated eval database."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base

EVALS_DATABASE_URL = os.environ.get(
    "EVALS_DATABASE_URL", "postgresql://evals:evals@localhost:55432/evals"
)

_engine = None


def get_eval_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(EVALS_DATABASE_URL)
    return _engine


def create_schema() -> None:
    """Create pgvector extension and all app tables in the eval DB."""
    engine = get_eval_engine()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)


def get_eval_session() -> Session:
    return sessionmaker(bind=get_eval_engine())()
```

(Verify `app.database` exposes `Base`; it does — models import `from app.database import Base`.)

- [ ] **Step 3: `backend/evals/seed.py`**

```python
"""Seed a small, known video library for golden-dataset evals.

Idempotent: running twice leaves one eval user with the same 15 videos.
The eval user's last_sync_at is fixed so freshness-caveat cases are stable.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.tag import Tag
from app.models.user import User
from app.models.video import Video
from app.services.embedding_service import EmbeddingService
from evals.db import create_schema, get_eval_session

EVAL_USER_EMAIL = "eval@example.com"
LAST_SYNC_AT = datetime(2026, 6, 20, tzinfo=timezone.utc)

# (title, channel, categories, tags, liked_at, duration_seconds)
VIDEOS = [
    ("Spicy Garlic Noodles in 15 Minutes", "Quick Eats", ["Food"], ["noodles", "recipe"], datetime(2026, 6, 18, tzinfo=timezone.utc), 540),
    ("Ultimate Ramen Broth Guide", "Noodle Lab", ["Food"], ["ramen", "recipe"], datetime(2026, 6, 15, tzinfo=timezone.utc), 900),
    ("One-Pot Pasta for Busy Weeknights", "Quick Eats", ["Food"], ["pasta", "recipe"], datetime(2026, 5, 30, tzinfo=timezone.utc), 480),
    ("No-Bake Mango Cheesecake", "Dessert Corner", ["Food"], ["dessert", "no-bake"], datetime(2026, 4, 10, tzinfo=timezone.utc), 720),
    ("Sourdough Starter Day by Day", "Bread Basics", ["Food"], ["baking", "sourdough"], datetime(2026, 3, 2, tzinfo=timezone.utc), 1100),
    ("Canon in D — Piano Cover", "Keys & Strings", ["Music"], ["piano", "classical"], datetime(2026, 6, 17, tzinfo=timezone.utc), 210),
    ("Lofi Beats to Focus To", "Chill Radio", ["Music"], ["lofi", "focus"], datetime(2026, 5, 12, tzinfo=timezone.utc), 3600),
    ("Tamil BGM Piano Medley", "Keys & Strings", ["Music"], ["piano", "bgm"], datetime(2026, 2, 20, tzinfo=timezone.utc), 300),
    ("Nginx Explained in 10 Minutes", "DevOps Daily", ["Technology"], ["nginx", "devops"], datetime(2026, 6, 19, tzinfo=timezone.utc), 600),
    ("PostgreSQL Indexing Deep Dive", "DB Internals", ["Technology"], ["postgres", "performance"], datetime(2026, 6, 1, tzinfo=timezone.utc), 1500),
    ("Kubernetes for Small Projects", "DevOps Daily", ["Technology"], ["kubernetes", "devops"], datetime(2026, 4, 25, tzinfo=timezone.utc), 1200),
    ("Rust Ownership Finally Explained", "Code Clarity", ["Technology"], ["rust", "programming"], datetime(2026, 3, 15, tzinfo=timezone.utc), 840),
    ("How Rockets Steer in Space", "Orbital Mechanics", ["Education"], ["space", "physics"], datetime(2026, 5, 5, tzinfo=timezone.utc), 660),
    ("The History of Tea Trade Routes", "Past Forward", ["Education"], ["history", "tea"], datetime(2026, 1, 8, tzinfo=timezone.utc), 980),
    ("Interview: A Century of Indian Classical Music", "Past Forward", ["Education", "Music"], ["history", "music"], datetime(2025, 12, 1, tzinfo=timezone.utc), 2400),
]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def seed(db: Session) -> int:
    """Create the eval user + library. Returns the eval user id."""
    user = db.query(User).filter(User.email == EVAL_USER_EMAIL).first()
    if user is not None:
        return user.id

    user = User(
        email=EVAL_USER_EMAIL,
        youtube_id="UC_EVAL_USER",
        name="Eval User",
        last_sync_at=LAST_SYNC_AT,
    )
    db.add(user)
    db.flush()

    cats: dict[str, Category] = {}
    tags: dict[str, Tag] = {}
    embedder = EmbeddingService()

    for title, channel, cat_names, tag_names, liked_at, duration in VIDEOS:
        video = Video(
            user_id=user.id,
            youtube_id=f"eval_{_slug(title)[:24]}",
            title=title,
            channel_title=channel,
            liked_at=liked_at,
            duration_seconds=duration,
            is_categorized=True,
        )
        for name in cat_names:
            if name not in cats:
                cats[name] = db.query(Category).filter(
                    Category.name == name
                ).first() or Category(name=name, slug=_slug(name))
                db.add(cats[name])
            video.categories.append(cats[name])
        for name in tag_names:
            if name not in tags:
                tags[name] = db.query(Tag).filter(
                    Tag.name == name
                ).first() or Tag(name=name, slug=_slug(name))
                db.add(tags[name])
            video.tags.append(tags[name])
        db.add(video)
        db.flush()
        # Real embedding so search_videos (semantic) works in evals.
        asyncio.run(embedder.embed_video(db, video))

    db.commit()
    return user.id


if __name__ == "__main__":
    create_schema()
    session = get_eval_session()
    try:
        user_id = seed(session)
        count = session.query(Video).filter(Video.user_id == user_id).count()
        print(f"Seeded eval user id={user_id} with {count} videos")
    finally:
        session.close()
```

**Implementer note:** check `app/models/video.py` / `app/models/user.py` for
required non-nullable columns beyond those set here (e.g. `access_token`); add
minimal values if the DB rejects the insert. Check `embed_video`'s exact
signature (`backend/app/services/embedding_service.py:92`) — it is
`async def embed_video(self, db: Session, video: Video) -> tuple[bool, str | None]`.
If `asyncio.run` per video is slow, batching via `embed_videos_batch` is fine.

- [ ] **Step 4: `backend/evals/dataset.yaml`**

```yaml
# Golden dataset for the chat agent. Seeded library: see evals/seed.py.
# The eval user's last_sync_at is 2026-06-20; newest liked video is 2026-06-19.
# Starts at 12 high-signal cases (spec targets ~20; the improvement loop in
# evals/README.md grows this file from real failed conversations).
cases:
  - id: recent-likes-3
    message: "what are my last 3 liked videos?"
    expected_tools: [filter_videos]
    forbid_tools: [search_videos]
    expected_titles_any:
      - "Nginx Explained in 10 Minutes"
      - "Spicy Garlic Noodles in 15 Minutes"
      - "Ultimate Ramen Broth Guide"
    expect_freshness_caveat: false

  - id: food-recent
    message: "did I like any food videos in the last 30 days?"
    expected_tools: [filter_videos]
    expected_titles_any:
      - "Spicy Garlic Noodles in 15 Minutes"
      - "Ultimate Ramen Broth Guide"
    expect_freshness_caveat: false

  - id: noodles-search
    message: "find my videos about noodles"
    expected_tools: [search_videos, filter_videos]  # either is acceptable
    expected_titles_any:
      - "Spicy Garlic Noodles in 15 Minutes"
      - "Ultimate Ramen Broth Guide"
    expect_freshness_caveat: false

  - id: freshness-window
    message: "show me videos I liked this week"
    expected_tools: [filter_videos]
    expected_titles_any: []
    expect_freshness_caveat: true

  - id: stats-overview
    message: "how many videos do I have in total?"
    expected_tools: [get_video_stats]
    expected_titles_any: []
    expect_freshness_caveat: false

  - id: top-categories
    message: "what are my top categories?"
    expected_tools: [get_video_stats]
    expected_titles_any: []
    expect_freshness_caveat: false

  - id: piano-topic
    message: "any piano videos in my library?"
    expected_tools: [search_videos, filter_videos]
    expected_titles_any:
      - "Canon in D — Piano Cover"
      - "Tamil BGM Piano Medley"
    expect_freshness_caveat: false

  - id: duration-filter
    message: "show me food videos under 10 minutes"
    expected_tools: [filter_videos]
    expected_titles_any:
      - "Spicy Garlic Noodles in 15 Minutes"
      - "One-Pot Pasta for Busy Weeknights"
    expect_freshness_caveat: false

  - id: playlist-confirm-first
    message: "create a playlist called Cooking Night from my food videos"
    expected_tools: [filter_videos, search_videos]
    forbid_tools: [create_playlist]  # must confirm selection before creating
    expected_titles_any: []
    expect_freshness_caveat: false

  - id: temporal-trends
    message: "how did my interests change over the last year?"
    expected_tools: [get_temporal_trends]
    expected_titles_any: []
    expect_freshness_caveat: false

  - id: tech-recent
    message: "latest tech videos I liked"
    expected_tools: [filter_videos]
    expected_titles_any:
      - "Nginx Explained in 10 Minutes"
      - "PostgreSQL Indexing Deep Dive"
    expect_freshness_caveat: false

  - id: nonexistent-topic
    message: "do I have any videos about scuba diving?"
    expected_tools: [search_videos]
    expected_titles_any: []
    expect_freshness_caveat: false
```

- [ ] **Step 5: Write the failing dataset test**

Create `backend/tests/test_evals_dataset.py`:

```python
"""Sanity checks on the golden dataset file (no DB, no network)."""

from pathlib import Path

import yaml

DATASET = Path(__file__).parent.parent / "evals" / "dataset.yaml"
KNOWN_TOOLS = {
    "search_videos",
    "filter_videos",
    "get_video_stats",
    "create_playlist",
    "get_temporal_trends",
}


def _cases() -> list[dict]:
    return yaml.safe_load(DATASET.read_text())["cases"]


def test_dataset_has_at_least_ten_cases() -> None:
    assert len(_cases()) >= 10


def test_all_cases_well_formed() -> None:
    seen_ids = set()
    for case in _cases():
        assert case["id"] not in seen_ids
        seen_ids.add(case["id"])
        assert case["message"].strip()
        assert set(case["expected_tools"]) <= KNOWN_TOOLS
        assert set(case.get("forbid_tools", [])) <= KNOWN_TOOLS
        assert isinstance(case["expected_titles_any"], list)
        assert isinstance(case["expect_freshness_caveat"], bool)
```

- [ ] **Step 6: Run tests (RED then GREEN)**

Run: `cd backend && poetry run pytest tests/test_evals_dataset.py -v`
First run may fail if `yaml` isn't importable → `poetry add pyyaml` + add locked version to `requirements.txt` is NOT needed (evals are dev-only) — instead: `poetry add --group dev pyyaml` (requirements.txt untouched since Vercel never imports evals). Expected after files exist: 2 passed.

- [ ] **Step 7: Seed run (requires Docker)**

```bash
cd backend && docker compose -f docker-compose.evals.yml up -d
poetry run python -m evals.seed
```

Expected: `Seeded eval user id=1 with 15 videos`. Re-run → same output (idempotent). Requires `OPENAI_API_KEY` in env for embeddings. If Docker is unavailable in the execution environment, mark this step deferred and note it in the report — the dataset tests above still gate the task.

- [ ] **Step 8: Quality gate + commit**

Run: `cd backend && poetry run black . && poetry run ruff check . && poetry run mypy . && poetry run pytest`

```bash
git add backend/docker-compose.evals.yml backend/evals backend/tests/test_evals_dataset.py backend/pyproject.toml backend/poetry.lock
git commit -m "feat: eval database, seed library, and golden dataset

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Deterministic scorers

**Files:**
- Create: `backend/evals/scorers.py`
- Test: `backend/tests/test_evals_scorers.py`

**Interfaces:**
- Consumes: dataset case dicts (Task 3 keys).
- Produces (for Task 5): `score_case(case: dict, answer: str, tool_events: list[dict]) -> dict[str, float]` where `tool_events` is `[{"tool": name, "arguments": {...}, "result": ...}, ...]` and the returned dict has keys `tool_choice`, `groundedness`, `expected_content`, `freshness_caveat` (each 0.0 or 1.0).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_evals_scorers.py`:

```python
"""Scorer unit tests with canned agent outputs — no DB, no OpenAI."""

from evals.scorers import score_case

CASE = {
    "id": "recent-likes-3",
    "message": "what are my last 3 liked videos?",
    "expected_tools": ["filter_videos"],
    "forbid_tools": ["search_videos"],
    "expected_titles_any": ["Nginx Explained in 10 Minutes"],
    "expect_freshness_caveat": False,
}

GOOD_EVENTS = [
    {
        "tool": "filter_videos",
        "arguments": {"limit": 3},
        "result": [
            {"id": 1, "title": "Nginx Explained in 10 Minutes"},
            {"id": 2, "title": "Canon in D — Piano Cover"},
        ],
    }
]


def test_perfect_run_scores_all_ones() -> None:
    answer = "Your last liked videos include Nginx Explained in 10 Minutes and Canon in D — Piano Cover."
    scores = score_case(CASE, answer, GOOD_EVENTS)
    assert scores == {
        "tool_choice": 1.0,
        "groundedness": 1.0,
        "expected_content": 1.0,
        "freshness_caveat": 1.0,
    }


def test_forbidden_tool_fails_tool_choice() -> None:
    events = [{"tool": "search_videos", "arguments": {}, "result": []}]
    scores = score_case(CASE, "anything", events)
    assert scores["tool_choice"] == 0.0


def test_hallucinated_title_fails_groundedness() -> None:
    answer = "You liked 'Totally Invented Video' recently."
    scores = score_case(CASE, answer, GOOD_EVENTS)
    assert scores["groundedness"] == 0.0


def test_missing_expected_content() -> None:
    answer = "You liked Canon in D — Piano Cover."
    scores = score_case(CASE, answer, GOOD_EVENTS)
    assert scores["expected_content"] == 0.0


def test_freshness_caveat_required_and_present() -> None:
    case = {**CASE, "expect_freshness_caveat": True, "expected_titles_any": []}
    answer = "I found nothing — note your library was last synced on 2026-06-20, so newer likes may be missing."
    scores = score_case(case, answer, GOOD_EVENTS)
    assert scores["freshness_caveat"] == 1.0


def test_freshness_caveat_required_but_absent() -> None:
    case = {**CASE, "expect_freshness_caveat": True, "expected_titles_any": []}
    scores = score_case(case, "You have no videos this week.", GOOD_EVENTS)
    assert scores["freshness_caveat"] == 0.0
```

- [ ] **Step 2: Run to verify RED**

Run: `cd backend && poetry run pytest tests/test_evals_scorers.py -v`
Expected: FAIL — `ModuleNotFoundError: evals.scorers`.

- [ ] **Step 3: Implement `backend/evals/scorers.py`**

```python
"""Deterministic 0/1 scorers for golden-dataset eval runs.

No LLM involvement: every score is computable from the case definition, the
agent's final answer text, and the recorded tool events.
"""

from __future__ import annotations

import re
from typing import Any

# Words that signal the agent acknowledged possibly-stale data.
_FRESHNESS_MARKERS = re.compile(
    r"last sync|synced|out of date|may be missing|not.{0,20}synced|sync.{0,20}dashboard",
    re.IGNORECASE,
)


def _result_titles(tool_events: list[dict[str, Any]]) -> set[str]:
    titles: set[str] = set()
    for event in tool_events:
        result = event.get("result")
        items = result if isinstance(result, list) else []
        for item in items:
            if isinstance(item, dict) and item.get("title"):
                titles.add(str(item["title"]))
    return titles


def _answer_mentions_unknown_title(answer: str, known_titles: set[str]) -> bool:
    """Heuristic groundedness: quoted/Title-Case runs in the answer must
    appear in some tool result. We check known titles both ways to avoid
    parsing natural language: any known title mentioned is fine; an answer
    that lists 'video'-like quoted strings not in the results is flagged."""
    quoted = re.findall(r"[\"'‘’“”]([^\"'‘’“”]{8,90})[\"'‘’“”]", answer)
    for candidate in quoted:
        if candidate.strip() and candidate.strip() not in known_titles:
            return True
    return False


def score_case(
    case: dict[str, Any], answer: str, tool_events: list[dict[str, Any]]
) -> dict[str, float]:
    called = [e["tool"] for e in tool_events]

    # 1. Tool choice: at least one expected tool used, no forbidden tool used.
    expected_ok = (not case["expected_tools"]) or any(
        t in called for t in case["expected_tools"]
    )
    forbidden_used = any(t in called for t in case.get("forbid_tools", []))
    tool_choice = 1.0 if expected_ok and not forbidden_used else 0.0

    # 2. Groundedness: known titles referenced must come from tool results.
    known_titles = _result_titles(tool_events)
    grounded = not _answer_mentions_unknown_title(answer, known_titles)
    # Additionally: any expected title claimed must actually be in results.
    for title in case.get("expected_titles_any", []):
        if title in answer and title not in known_titles:
            grounded = False
    groundedness = 1.0 if grounded else 0.0

    # 3. Expected content: at least one expected title in the answer
    #    (vacuously true when none are expected).
    expected_titles = case.get("expected_titles_any", [])
    content_hit = (not expected_titles) or any(t in answer for t in expected_titles)
    expected_content = 1.0 if content_hit else 0.0

    # 4. Freshness caveat present when required (vacuously true otherwise).
    if case.get("expect_freshness_caveat"):
        freshness = 1.0 if _FRESHNESS_MARKERS.search(answer) else 0.0
    else:
        freshness = 1.0

    return {
        "tool_choice": tool_choice,
        "groundedness": groundedness,
        "expected_content": expected_content,
        "freshness_caveat": freshness,
    }
```

- [ ] **Step 4: Run to verify GREEN**

Run: `cd backend && poetry run pytest tests/test_evals_scorers.py -v`
Expected: 6 passed.

- [ ] **Step 5: Quality gate + commit**

Run: `cd backend && poetry run black . && poetry run ruff check . && poetry run mypy . && poetry run pytest`

```bash
git add backend/evals/scorers.py backend/tests/test_evals_scorers.py
git commit -m "feat: deterministic scorers for chat agent evals

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Eval runner with Langfuse experiment upload

**Files:**
- Create: `backend/evals/run.py`
- Test: `backend/tests/test_evals_runner.py`

**Interfaces:**
- Consumes: `evals.db.get_eval_session/create_schema`, `evals.seed.seed`, `evals.scorers.score_case`, `AgentService.chat(session_id, message)` async generator yielding `ChatStreamEvent` (`type` in `{"tool_call", "tool_result", "message", "done", "error"}` — verify final-text event type in `agent_service.py` after line 789 and adjust `_collect`).
- Produces: `poetry run python -m evals.run [--dry-run]`.

- [ ] **Step 1: Write the failing test (dry-run path only)**

Create `backend/tests/test_evals_runner.py`:

```python
"""Runner plumbing tests via --dry-run (no DB, no OpenAI, no Langfuse)."""

from evals.run import run_dry


def test_dry_run_scores_all_cases() -> None:
    results = run_dry()
    assert len(results) >= 10
    for r in results:
        assert set(r["scores"].keys()) == {
            "tool_choice",
            "groundedness",
            "expected_content",
            "freshness_caveat",
        }
```

- [ ] **Step 2: RED**

Run: `cd backend && poetry run pytest tests/test_evals_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: evals.run`.

- [ ] **Step 3: Implement `backend/evals/run.py`**

```python
"""Golden-dataset eval runner for the chat agent.

Usage:
    poetry run python -m evals.run            # real run (docker DB + OpenAI)
    poetry run python -m evals.run --dry-run  # scorer plumbing check, no I/O

Real runs execute each case against the actual AgentService on the seeded
eval library, score deterministically, print a table, and upload the run to
Langfuse via run_experiment (when Langfuse keys are configured).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path
from typing import Any

import yaml

DATASET_PATH = Path(__file__).parent / "dataset.yaml"


def load_cases() -> list[dict[str, Any]]:
    return yaml.safe_load(DATASET_PATH.read_text())["cases"]


def run_dry() -> list[dict[str, Any]]:
    """Score canned outputs for every case — validates plumbing, not the agent."""
    from evals.scorers import score_case

    results = []
    for case in load_cases():
        canned_events = [
            {
                "tool": (case["expected_tools"] or ["filter_videos"])[0],
                "arguments": {},
                "result": [{"id": 1, "title": t} for t in case["expected_titles_any"]],
            }
        ]
        canned_answer = " ".join(case["expected_titles_any"]) or (
            "Nothing found — note your library was last synced recently; "
            "newer likes may be missing until you sync."
        )
        results.append(
            {
                "id": case["id"],
                "scores": score_case(case, canned_answer, canned_events),
            }
        )
    return results


async def _run_case(agent, case: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Drive one chat turn; collect final text + tool events."""
    session_id = str(uuid.uuid4())
    answer_parts: list[str] = []
    tool_events: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}

    async for event in agent.chat(session_id, case["message"]):
        if event.type == "tool_call":
            pending[event.tool] = {"tool": event.tool, "arguments": event.arguments}
        elif event.type == "tool_result":
            entry = pending.pop(event.tool, {"tool": event.tool, "arguments": {}})
            entry["result"] = event.result
            tool_events.append(entry)
        elif event.content:
            answer_parts.append(event.content)
    return "".join(answer_parts), tool_events


def run_real() -> list[dict[str, Any]]:
    from app.services.agent_service import AgentService
    from evals.db import create_schema, get_eval_session
    from evals.scorers import score_case
    from evals.seed import seed

    create_schema()
    db = get_eval_session()
    try:
        user_id = seed(db)
        results = []
        for case in load_cases():
            agent = AgentService(user_id=user_id, db=db)
            answer, tool_events = asyncio.run(_run_case(agent, case))
            scores = score_case(case, answer, tool_events)
            results.append(
                {
                    "id": case["id"],
                    "message": case["message"],
                    "answer": answer,
                    "tool_events": tool_events,
                    "scores": scores,
                }
            )
            flags = " ".join(
                f"{k}={'PASS' if v else 'FAIL'}" for k, v in scores.items()
            )
            print(f"[{case['id']}] {flags}")
        _upload_to_langfuse(results)
        _print_summary(results)
        return results
    finally:
        db.close()


def _print_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    for metric in ("tool_choice", "groundedness", "expected_content", "freshness_caveat"):
        passed = sum(1 for r in results if r["scores"][metric] == 1.0)
        print(f"{metric}: {passed}/{total}")


def _upload_to_langfuse(results: list[dict[str, Any]]) -> None:
    """Upload as a Langfuse DATASET RUN so runs are comparable across versions.

    (Local-data run_experiment creates only traces, no dataset runs — the spec
    requires run-over-run score history, hence the dataset sync first.)
    Skipped without keys.
    """
    from datetime import datetime, timezone

    from app.observability import get_langfuse

    client = get_langfuse()
    if client is None:
        print("Langfuse not configured — skipping experiment upload.")
        return
    from langfuse import Evaluation

    dataset_name = "chat-agent-golden"
    try:
        client.create_dataset(name=dataset_name)
    except Exception:
        pass  # already exists
    for r in results:
        # Deterministic id makes re-runs upsert instead of duplicating items.
        client.create_dataset_item(
            dataset_name=dataset_name,
            id=f"golden-{r['id']}",
            input=r["message"],
            metadata={"case_id": r["id"]},
        )

    by_input = {r["message"]: r for r in results}

    def task(*, item, **kwargs):
        return by_input[item.input]["answer"]

    def make_evaluator(metric: str):
        def evaluator(*, input, output, **kwargs):
            return Evaluation(name=metric, value=by_input[input]["scores"][metric])

        evaluator.__name__ = f"{metric}_evaluator"
        return evaluator

    dataset = client.get_dataset(dataset_name)
    run_name = f"golden-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
    result = dataset.run_experiment(
        name=run_name,
        description="Deterministic golden-dataset run",
        task=task,
        evaluators=[
            make_evaluator(m)
            for m in ("tool_choice", "groundedness", "expected_content", "freshness_caveat")
        ],
    )
    print(result.format())
    client.flush()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        for r in run_dry():
            print(r["id"], r["scores"])
    else:
        run_real()
```

**Implementer notes:**
- Verify the final-text event: read `agent_service.py` lines 789-830 for how
  `final_text` is yielded (`ChatStreamEvent(type=?, content=final_text)`), and
  make `_run_case` collect exactly that event type. The `elif event.content:`
  fallback above works if the final event carries `content`, but confirm.
- The `pending[event.tool]` pairing assumes one call per tool per iteration —
  acceptable for evals; note it if the agent ever parallel-calls one tool twice.
- `run_experiment` signature verified against current docs
  (langfuse.com/docs/evaluation/experiments/experiments-via-sdk): local-data
  experiments create one trace per item and report `Evaluation` scores. If the
  installed SDK version errors on it, fetch that page and adapt — do not guess.
- Redis is optional: `get_redis()` degrades to no-op caching when no local
  Redis runs (verified earlier in this repo), which is desirable for evals.

- [ ] **Step 4: GREEN (dry-run)**

Run: `cd backend && poetry run pytest tests/test_evals_runner.py -v`
Expected: 1 passed.
Also run: `poetry run python -m evals.run --dry-run` — prints one line per case, all scores 1.0.

- [ ] **Step 5: Real eval run (requires Docker + OPENAI_API_KEY; defer if unavailable)**

```bash
cd backend && docker compose -f docker-compose.evals.yml up -d
poetry run python -m evals.run
```

Expected: a PASS/FAIL line per case, a summary block, and (with Langfuse keys) an experiment named `chat-agent-golden` visible under Langfuse → Datasets/Experiments with 4 score columns. Some cases may legitimately FAIL — record which; that's the baseline measurement, not a task failure. If environment prevents this, mark deferred with reasons.

- [ ] **Step 6: Quality gate + commit**

Run: `cd backend && poetry run black . && poetry run ruff check . && poetry run mypy . && poetry run pytest`

```bash
git add backend/evals/run.py backend/tests/test_evals_runner.py
git commit -m "feat: golden-dataset eval runner with Langfuse experiment upload

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Judge prompts + Langfuse UI configuration guide

**Files:**
- Create: `backend/evals/judges/groundedness.md`
- Create: `backend/evals/judges/helpfulness.md`
- Create: `backend/evals/README.md`

**Interfaces:** none consumed/produced in code — these are versioned artifacts + operator docs.

- [ ] **Step 1: `backend/evals/judges/groundedness.md`**

```markdown
# Judge: Groundedness (configure in Langfuse UI → Evaluators)

Model: any strong small model (e.g. gpt-5-mini equivalent). Sampling: 100%.
Target: production traces named `chat-turn`.

## Prompt

You are grading a YouTube library assistant's answer for groundedness.

Trace input (user message): {{input}}
Assistant answer: {{output}}
Tool results available to the assistant (from the trace's tool spans): {{metadata}}

Score 1 if every specific video the answer mentions (titles, channels,
liked dates) appears in the tool results. Score 0 if the answer asserts any
video, title, channel, or date that is not present in tool results.
Clarifying questions and generic statements with no specific claims score 1.

Respond with a score of 0 or 1 and a one-sentence reason.
```

- [ ] **Step 2: `backend/evals/judges/helpfulness.md`**

```markdown
# Judge: Helpfulness / Resolution (configure in Langfuse UI → Evaluators)

Model: any strong small model. Sampling: 100%.
Target: production traces named `chat-turn`.

## Prompt

You are grading a YouTube library assistant's answer for helpfulness.

User message: {{input}}
Assistant answer: {{output}}

Score 1 if the answer either (a) directly answers the question with concrete
results, or (b) asks ONE precise clarifying question that is genuinely needed.
Score 0 if it: answers a different question, asks for clarification that the
message already provided, claims inability without suggesting a next step, or
buries the answer in unnecessary options.

Respond with a score of 0 or 1 and a one-sentence reason.
```

- [ ] **Step 3: `backend/evals/README.md`**

```markdown
# Chat Agent Evals

## Offline golden dataset

    docker compose -f docker-compose.evals.yml up -d
    poetry run python -m evals.run            # real run (needs OPENAI_API_KEY)
    poetry run python -m evals.run --dry-run  # plumbing check, no I/O

Run before/after ANY change to the system prompt, tool definitions, or model.
Results upload to Langfuse (experiment `chat-agent-golden`) when
LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY are set.

## Live LLM-as-judge (one-time Langfuse UI setup)

1. Langfuse → your project → Evaluators → + New evaluator.
2. Create "groundedness" from `judges/groundedness.md` (prompt + settings).
3. Create "helpfulness" from `judges/helpfulness.md`.
4. Target filter: trace name = `chat-turn`. Sampling: 100%.
5. Provide an OpenAI API key under Settings → LLM connections if not already.

Judge prompts are versioned here; the UI is the execution environment. If you
edit a prompt, update BOTH the UI and the file in the same change.

## The improvement loop

Bad live conversation → open its trace (Traces → filter `chat-turn`) → read
tool spans → add a case to `dataset.yaml` reproducing it → fix prompt/tool →
`python -m evals.run` shows the case pass with no regressions → deploy →
judge scores confirm on live traces.
```

- [ ] **Step 4: Commit**

```bash
git add backend/evals/judges backend/evals/README.md
git commit -m "docs: judge prompts and eval runbook

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Manual (user or operator): configure both evaluators in the Langfuse UI per the README.** Verification deferred to first post-deploy traces.

---

### Task 7: Final verification

**Files:** none.

- [ ] **Step 1: Full gates**

Run: `cd backend && poetry run black . && poetry run ruff check . && poetry run mypy . && poetry run pytest`
Expected: all pass (existing 14 tests + new observability/eval tests).

- [ ] **Step 2: requirements.txt audit (deployment-critical)**

`langfuse` (and its transitive runtime deps if Vercel build complains) present in `backend/requirements.txt` with the locked version; `pyyaml` deliberately dev-only. Confirm with `grep -i langfuse backend/requirements.txt`.

- [ ] **Step 3: No-op regression proof**

Run the full test suite with Langfuse vars explicitly unset:
`cd backend && env -u LANGFUSE_PUBLIC_KEY -u LANGFUSE_SECRET_KEY poetry run pytest`
Expected: all pass.

- [ ] **Step 4: Report**

Summarize: what's traced, how to run evals, baseline eval scores (if the real run happened), what remains manual (Langfuse UI evaluator setup, post-deploy trace check). Do NOT push — ask the user about push/PR.
