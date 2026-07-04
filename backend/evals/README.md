# Chat Agent Evals

## Offline golden dataset

    docker compose -f docker-compose.evals.yml up -d
    poetry run python -m evals.run            # real run (needs OPENAI_API_KEY)
    poetry run python -m evals.run --dry-run  # plumbing check, no I/O

Run before/after ANY change to the system prompt, tool definitions, or model.
Results upload to Langfuse (experiment `chat-agent-golden`) when
LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY are set.

### Run environment notes

- **Model parity:** Export the production model explicitly for runs: `OPENAI_MODEL=gpt-5.2`. Local `.env` may pin an older model that rejects the agent's `reasoning.effort` parameter, invalidating tool_choice scores.
- **Env sourcing:** Langfuse SDK reads OS environment variables, not Pydantic settings. Source `.env` before runs: `set -a; source .env; set +a`. Then unset `CORS_ORIGINS` afterward (its JSON-array value breaks when exported as a plain shell var; Pydantic re-parses `.env` itself).

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
