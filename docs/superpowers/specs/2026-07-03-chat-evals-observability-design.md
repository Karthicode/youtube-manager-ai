# Chat Agent Observability + Eval Pipeline

**Date:** 2026-07-03
**Status:** Approved

## Goal

Give the chat agent full observability (trace every conversation turn: model
calls, tool calls + results, data sources, latency, tokens, errors) and a
repeatable eval pipeline, so agent regressions and failures are diagnosed
from data instead of ad-hoc debugging.

Motivating incident: the agent answered "last 3 liked videos" with
March/October videos (used semantic `search_videos` instead of the
recency-sorted `filter_videos`) and asserted "no recent food videos" without
knowing its library ended at the last sync. Diagnosis required a manual
debugging session because no trace of tool calls/results existed.

**Platform decision:** Langfuse Cloud (free tier). One integration covers
tracing, session views, datasets, score history, and managed LLM-as-judge
evals. Self-hostable later if needed.

## Current state (what exists)

- `AgentService` (`backend/app/services/agent_service.py`): OpenAI Responses
  API loop (max 10 tool iterations), 5 tools, Redis caching of system prompt
  (5 min) and read-only tool results (5 min).
- `ChatSession`/`ChatMessage` models persist messages with `tool_calls_json`
  — but no tool results, timing, tokens, or trace view.
- Chat endpoint streams JSON-lines events (`ChatStreamEvent`) incl. tool
  events. Backend runs on Vercel serverless.

## Phase 1: Tracing (Langfuse SDK integration)

**Approach:** Langfuse Python SDK decorators + explicit tool spans
(alternatives considered: OpenTelemetry→OTLP export — heavier, no extra
insight at this scale; manual low-level Langfuse API — more code, same UI).

- **Dependency/config:** `langfuse` package (sync `requirements.txt`!).
  Env vars `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.
  **No-op when keys are unset** — dev/test unaffected; prod kill-switch is
  removing the env vars.
- **Trace structure:** one trace per chat turn. Metadata: Langfuse
  `session_id` = chat `session_id` (groups turns in the session view),
  `user_id`, `prompt_version` tag (bump manually when the system prompt
  changes). Trace input = user message; output = final assistant text.
- **Auto-captured generations:** wrap the OpenAI client with Langfuse's
  OpenAI integration — every model call in the tool loop (tool-selection
  iterations + final synthesis) becomes a generation span with model,
  tokens, cost, latency.
- **Tool spans:** explicit span per `_execute_tool` call: tool name,
  arguments, full result payload, duration, `cache_hit` boolean (Redis
  tool-result cache), and error capture when a tool raises (the current
  swallowed `{"error": ...}` becomes a visible error span).
- **Serverless flush:** `langfuse.flush()` in a `finally` at the end of the
  chat request — mandatory on Vercel or batched events are lost when the
  function freezes.

## Phase 2: Golden-dataset offline eval

**Location:** `backend/evals/` — `dataset.yaml`, `seed.py`, `run.py`,
`scorers.py`, plus `docker-compose.evals.yml` (Postgres + pgvector).

- **Seeded test library:** `seed.py` creates an eval user + ~15 videos with
  known titles/categories/tags/liked_at (several food/cooking incl. a
  noodles video; music; tech; some liked after the fixed `last_sync_at` to
  exercise freshness behavior) in the local eval DB. Real embeddings
  generated once at seed time. Never touches prod.
- **Dataset cases (~20 initially, seeded from the real failure
  conversation):** each case = user message (+ optional follow-up),
  `expected_tools`, `expected_titles_any`, `expect_freshness_caveat`,
  `forbidden_behavior` notes.
- **Deterministic scorers (no LLM):**
  1. tool-choice correctness (expected tool called),
  2. groundedness (every video title in the answer exists in that turn's
     tool results),
  3. expected-content hit,
  4. freshness-caveat presence when required.
  Each scores 0/1 per case.
- **Runner:** `poetry run python -m evals.run` — executes cases against the
  real `AgentService` (real OpenAI calls, ~$0.05/run), prints a pass/fail
  table, uploads the run to Langfuse as a dataset run for cross-version
  score history. `--dry-run` mode scores canned responses without OpenAI
  calls (CI-safe test of the scorers themselves).
- **Usage rule:** run before/after any change to the system prompt, tool
  definitions, or model choice.

## Phase 3: LLM-as-judge on live traces

- Two managed evaluators configured in the Langfuse UI, 100% sampling
  (single-user volume):
  1. **Groundedness** — answer references only videos present in the
     trace's tool results;
  2. **Helpfulness/resolution** — the assistant answered the question or
     productively clarified.
- Judge prompts are committed to `backend/evals/judges/*.md` for versioning
  even though execution happens in Langfuse.

## The improvement loop (what this buys)

Bad live conversation → open its Langfuse trace → see exact tool calls +
results → add the conversation as a golden-dataset case → fix prompt/tool →
`evals.run` shows the case flip to pass with no regressions → deploy →
judge scores on live traces confirm.

## Error handling & testing

- Tracing code paths unit-tested with Langfuse disabled (no-op) and with a
  fake client asserting span attribution (tool name, cache_hit, error
  capture).
- Eval scorers unit-tested with canned agent outputs (`--dry-run` fixtures).
- Tracing failures must never break chat: all Langfuse calls wrapped so an
  exporter error logs a warning and the request proceeds.
- Quality gates: `black . && ruff check . && mypy .` + pytest (backend).

## Out of scope

- Frontend changes (no thumbs up/down feedback buttons in this iteration —
  deliberately deferred).
- CI wiring for the eval runner (add once the suite is stable).
- Self-hosting Langfuse.
- Tracing for non-chat AI features (categorization, taste profile) — same
  pattern can be extended later.
