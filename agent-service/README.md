# Agent Service

Internal FastAPI service for the Enterprise Data Copilot analysis workflow.

P4 provides a vendor-neutral `LLMProvider`, an OpenRouter/OpenAI-compatible adapter,
strict Pydantic structured output, bounded retries and a no-network Fake LLM.

The fixed-SQL safety slice adds a SQLGlot AST guard, PostgreSQL read-only executor,
bounded results and an audit port. It is deliberately independent of model output.

P5 adds a safe NL2SQL pipeline: prompt-level request rejection, relevant-table selection,
structured analysis plans and SQL, column allowlists, deterministic query-shape checks,
PostgreSQL JSON `EXPLAIN` cost gates and at most two repairs using safe error codes only.

P6 adds bounded Markdown/PDF ingestion, versioned tenant-scoped metric chunks,
PostgreSQL full-text search, pgvector cosine search, weighted RRF, citations, refusal
thresholds and a 24-case lexical/vector/hybrid evaluation.

P7 adds the durable LangGraph workflow, PostgreSQL checkpoints, strict checkpoint
deserialization, Java-owned one-time approvals, redacted step callbacks and a hard two-repair
limit. Production graph actions reuse the P5 SQL boundary and P6 retrieval service.

P8 keeps this service internal: Java now invokes the start endpoint from a bounded background
executor, retries with the same job idempotency key, persists the returned final state, and exposes
Redis-backed SSE progress to browsers. The Python service still never exposes a browser endpoint.

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
Run `make verify-p6` with the platform database running to exercise full-text and pgvector
retrieval, or `make rag-eval` for the deterministic offline comparison.
Run `make verify-p7` to disconnect and recreate the PostgreSQL checkpointer before resuming an
interrupted approval flow, and to verify duplicate approval and loop-limit behavior.
