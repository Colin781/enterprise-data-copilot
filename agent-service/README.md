# Agent Service

Internal FastAPI service for the Enterprise Data Copilot analysis workflow.

P4 provides a vendor-neutral `LLMProvider`, an OpenRouter/OpenAI-compatible adapter,
strict Pydantic structured output, bounded retries and a no-network Fake LLM.

The fixed-SQL safety slice adds a SQLGlot AST guard, PostgreSQL read-only executor,
bounded results and an audit port. It is deliberately independent of model output.

P5 adds a safe NL2SQL pipeline: prompt-level request rejection, relevant-table selection,
structured analysis plans and SQL, column allowlists, deterministic query-shape checks,
PostgreSQL JSON `EXPLAIN` cost gates and at most two repairs using safe error codes only.
RAG and LangGraph orchestration remain intentionally deferred to P6 and P7.

```bash
uv sync --all-groups
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Real model calls are not part of automated tests. Configure them through the `LLM_*`
variables documented in the repository `.env.example`; never put a real key in source code.
Run `make verify-p5` from the repository root while the business database is running to
exercise the full P5 pipeline against PostgreSQL without spending model credits.
