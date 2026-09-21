SHELL := /bin/sh

ifneq (,$(wildcard .env))
include .env
export
endif

UV ?= uv
PNPM ?= pnpm

.PHONY: help env setup dev dev-platform dev-agent dev-web test contract-test lint build compose-config compose-up compose-down stack-config stack-up stack-down load-northwind verify-readonly verify-p2 verify-safety verify-p4 verify-p5 verify-p6 verify-p7 verify-p8 verify-p9 verify-p10 verify-p11 verify-p12 verify-all rag-eval p10-eval p10-eval-real p11-load

help:
	@printf '%s\n' \
		'make env             Create .env from the non-secret template' \
		'make setup           Install Python and Web dependencies' \
		'make dev             Start dependencies and all three services' \
		'make test            Run Java and Python tests' \
		'make contract-test   Validate OpenAPI and event contracts' \
		'make lint            Run Java, Python and Web static checks' \
		'make build           Build Java and Web production artifacts' \
		'make compose-up      Start PostgreSQL and Redis' \
		'make compose-down    Stop local dependencies' \
		'make stack-up        Build and start the complete observable application stack' \
		'make stack-down      Stop the complete application stack' \
		'make load-northwind  Idempotently load the fixed Northwind fixture' \
		'make verify-readonly Verify the business database security boundary' \
		'make verify-p2       Run all real-database P2 acceptance tests' \
		'make verify-safety   Run the fixed-SQL safety slice against PostgreSQL' \
		'make verify-p4       Run Fake LLM and provider adapter acceptance tests' \
		'make verify-p5       Run safe NL2SQL tests and real execution evaluation' \
		'make verify-p6       Run RAG tests against PostgreSQL and pgvector' \
		'make verify-p7       Verify durable LangGraph recovery and approval guards' \
		'make verify-p8       Verify async execution, Redis replay and SSE recovery' \
		'make verify-p9       Verify the Web UI, structured charts and P9 API support' \
		'make verify-p10      Verify 50+ NL2SQL, 20+ RAG and failure classification' \
		'make verify-p11      Verify trace, metrics, deployment and load-test assets' \
		'make verify-p12      Verify portfolio evidence and final documentation' \
		'make verify-all      Run the complete P1-P12 local acceptance suite' \
		'make rag-eval        Compare lexical, vector and hybrid retrieval baselines' \
		'make p10-eval        Write the deterministic full P10 baseline report' \
		'make p10-eval-real   Explicitly send the P10 suite to the configured model' \
		'make p11-load        Run the no-model-cost concurrent task and SSE load test'

env:
	@test -f .env || cp .env.example .env

setup:
	cd agent-service && $(UV) sync --all-groups
	cd web && $(PNPM) install --frozen-lockfile

dev: compose-up
	$(MAKE) -j3 dev-platform dev-agent dev-web

dev-platform:
	cd platform-api && ./mvnw spring-boot:run

dev-agent:
	cd agent-service && $(UV) run uvicorn app.main:app --reload --port $${AGENT_SERVICE_PORT:-8000}

dev-web:
	cd web && $(PNPM) dev --port $${WEB_PORT:-3000}

test:
	cd platform-api && ./mvnw test
	cd agent-service && $(UV) run pytest
	cd web && node --experimental-strip-types --test tests/*.test.ts

contract-test:
	cd agent-service && $(UV) run pytest tests/test_contracts.py

lint:
	cd platform-api && ./mvnw spotless:check
	cd agent-service && $(UV) run ruff check .
	cd agent-service && $(UV) run ruff format --check .
	cd web && ./node_modules/.bin/eslint .
	cd web && ./node_modules/.bin/tsc --noEmit

build:
	cd platform-api && ./mvnw package
	cd web && ./node_modules/.bin/next build

compose-config:
	docker compose --env-file .env.example config --quiet

compose-up: env
	docker compose up -d --wait
	$(MAKE) load-northwind

load-northwind:
	./scripts/load-northwind.sh

compose-down:
	docker compose down

stack-config:
	docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.full.yml config --quiet

stack-up: env
	docker compose -f docker-compose.yml -f docker-compose.full.yml up -d --build --wait
	$(MAKE) load-northwind

stack-down:
	docker compose -f docker-compose.yml -f docker-compose.full.yml down

verify-readonly:
	./scripts/verify-business-db-readonly.sh

verify-p2: verify-readonly
	cd agent-service && RUN_P2_INTEGRATION=1 $(UV) run pytest tests/test_p2_integration.py

verify-safety:
	cd agent-service && RUN_SAFETY_INTEGRATION=1 $(UV) run pytest tests/test_query_safety.py tests/test_safety_integration.py

verify-p4:
	cd agent-service && $(UV) run pytest tests/test_llm_structured.py tests/test_openai_compatible_provider.py

verify-p5:
	cd agent-service && RUN_P5_INTEGRATION=1 $(UV) run pytest tests/test_nl2sql.py tests/test_p5_integration.py

verify-p6:
	cd agent-service && RUN_P6_INTEGRATION=1 $(UV) run pytest tests/test_retrieval.py tests/test_p6_integration.py

verify-p7:
	cd agent-service && RUN_P7_INTEGRATION=1 $(UV) run pytest \
		tests/test_agent_actions.py tests/test_agent_workflow.py \
		tests/test_agent_api.py tests/test_p7_integration.py

verify-p8:
	cd platform-api && ./mvnw -Dtest=AsyncSseIntegrationTest test

verify-p9:
	cd web && node --experimental-strip-types --test tests/*.test.ts
	cd web && ./node_modules/.bin/eslint .
	cd web && ./node_modules/.bin/tsc --noEmit
	cd web && ./node_modules/.bin/next build
	cd platform-api && ./mvnw -Dtest=PlatformSecurityIntegrationTest,AsyncSseIntegrationTest test
	cd agent-service && $(UV) run pytest tests/test_charting.py tests/test_knowledge_api.py tests/test_contracts.py

verify-p10:
	cd platform-api && ./mvnw -Dtest=HttpAgentRunClientFailureTest test
	cd agent-service && $(UV) run pytest tests/test_p10_evaluation.py
	cd agent-service && RUN_P10_INTEGRATION=1 $(UV) run pytest tests/test_p10_integration.py

verify-p11: stack-config
	cd platform-api && ./mvnw -Dtest=TraceIdFilterTest,HttpAgentRunClientFailureTest test
	cd agent-service && $(UV) run pytest tests/test_health.py tests/test_observability.py tests/test_agent_workflow.py

verify-p12:
	$(UV) run --project agent-service python scripts/verify-portfolio-evidence.py

verify-all: lint test contract-test verify-p2 verify-safety verify-p4 verify-p5 verify-p6 verify-p7 verify-p8 verify-p9 verify-p10 verify-p11 verify-p12

rag-eval:
	cd agent-service && $(UV) run python -m app.retrieval.cli \
		--document ../knowledge/northwind/retail-metrics-v1.md \
		--cases ../evaluation/northwind/rag-gold-v1.jsonl

p10-eval:
	cd agent-service && $(UV) run python -m app.evaluation.cli \
		--nl2sql-cases ../evaluation/northwind/nl2sql-gold-v2.jsonl \
		--dangerous-cases ../evaluation/northwind/dangerous-questions-v1.jsonl \
		--rag-cases ../evaluation/northwind/rag-gold-v1.jsonl \
		--metric-document ../knowledge/northwind/retail-metrics-v1.md \
		--schema-snapshot ../metadata/northwind-schema-v1.json \
		--output ../evaluation/northwind/p10-offline-baseline.json

p10-eval-real:
	cd agent-service && $(UV) run python -m app.evaluation.cli \
		--nl2sql-cases ../evaluation/northwind/nl2sql-gold-v2.jsonl \
		--dangerous-cases ../evaluation/northwind/dangerous-questions-v1.jsonl \
		--rag-cases ../evaluation/northwind/rag-gold-v1.jsonl \
		--metric-document ../knowledge/northwind/retail-metrics-v1.md \
		--schema-snapshot ../metadata/northwind-schema-v1.json \
		--output ../evaluation/northwind/p10-real-model-report.json \
		--mode configured_model \
		--allow-external-model $(P10_MODEL_PRICE_ARGS)

p11-load:
	docker run --rm --add-host host.docker.internal:host-gateway \
		-e PLATFORM_BASE_URL=http://host.docker.internal:$${PLATFORM_API_HTTP_PORT:-8080} \
		-e P11_VUS=$${P11_VUS:-5} -e P11_DURATION=$${P11_DURATION:-15s} \
		-e P11_TENANT=$${PLATFORM_BOOTSTRAP_TENANT_SLUG:-northwind} \
		-e P11_EMAIL=$${PLATFORM_BOOTSTRAP_ANALYST_EMAIL:-analyst@northwind.local} \
		-e P11_PASSWORD=$${PLATFORM_BOOTSTRAP_PASSWORD:-change-me-demo} \
		-v "$(CURDIR)/performance/k6:/scripts:ro" grafana/k6:1.0.0 \
		run /scripts/p11-platform-and-sse.js
