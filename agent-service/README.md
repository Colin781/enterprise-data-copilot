# Agent Service

Internal FastAPI service for the Enterprise Data Copilot analysis workflow.

For current configuration and startup, follow the [local startup guide](../docs/current-local-startup-guide.md).
The [project reading guide](../docs/code-reading-guide.md) traces Web → Java → Python;
Java now uses unified layer packages, while Python retains the capability modules described below.
The P4–P8 paragraphs describe when each capability was introduced, not the project's current milestone.

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

Start from the repository root after configuring `.env` (keep Platform running in another terminal):

```bash
make compose-up
make dev-agent
```

The Makefile exports the root `.env`. Settings resolve their own `.env` relative to the working
directory: starting bare Uvicorn inside `agent-service/` does not automatically load the repository-root
file. Prefer `make dev-agent` rather than copying secrets into a second file. Do not `source .env`,
which contains values with spaces. Application health
does not certify model connectivity or a completed end-to-end analysis.

For dependency installation and tests, run from `agent-service/`:

```bash
uv sync --all-groups
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
