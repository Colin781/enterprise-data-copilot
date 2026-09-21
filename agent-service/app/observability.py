import hashlib
import re
import secrets
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from time import perf_counter

from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import (
    NonRecordingSpan,
    Span,
    SpanContext,
    SpanKind,
    Status,
    StatusCode,
    TraceFlags,
    TraceState,
    set_span_in_context,
)
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.settings import ObservabilitySettings, Settings

HTTP_REQUESTS = Counter(
    "copilot_agent_http_requests_total",
    "Agent HTTP requests by route and status.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "copilot_agent_http_request_duration_seconds",
    "Agent HTTP request latency.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
NODE_DURATION = Histogram(
    "copilot_agent_node_duration_seconds",
    "LangGraph node latency without questions, SQL, or result values.",
    ("node", "status"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
NODE_ERRORS = Counter(
    "copilot_agent_node_errors_total",
    "LangGraph node failures by stable error code.",
    ("node", "error_code"),
)
MODEL_TOKENS = Counter(
    "copilot_agent_model_tokens_total",
    "Language-model tokens reported by the provider.",
    ("provider", "model", "direction"),
)
SQL_REJECTIONS = Counter(
    "copilot_agent_sql_rejections_total",
    "Requests stopped by deterministic question or SQL policy.",
    ("reason_code",),
)

_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}")
_TRACE_ID = re.compile(r"[0-9a-f]{32}")
_configured = False


def configure_observability(settings: Settings, observability: ObservabilitySettings) -> None:
    global _configured
    if _configured or not observability.tracing_enabled:
        return
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.version,
                "deployment.environment.name": settings.environment,
            }
        )
    )
    if observability.otlp_http_endpoint is not None:
        endpoint = str(observability.otlp_http_endpoint).rstrip("/") + "/v1/traces"
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _configured = True


def trace_id_from_traceparent(value: str) -> str:
    parts = value.lower().split("-")
    if (
        len(parts) != 4
        or parts[0] != "00"
        or not _TRACE_ID.fullmatch(parts[1])
        or parts[1] == "0" * 32
        or not re.fullmatch(r"[0-9a-f]{16}", parts[2])
        or parts[2] == "0" * 16
        or not re.fullmatch(r"[0-9a-f]{2}", parts[3])
    ):
        raise ValueError("invalid W3C traceparent")
    return parts[1]


def normalize_trace_id(value: str) -> str:
    lowered = value.lower()
    if _TRACE_ID.fullmatch(lowered) and lowered != "0" * 32:
        return lowered
    return hashlib.sha256(value.encode()).hexdigest()[:32]


@contextmanager
def agent_node_span(node: str, trace_id: str) -> Iterator[Span]:
    parent = SpanContext(
        trace_id=int(normalize_trace_id(trace_id), 16),
        span_id=max(1, secrets.randbits(64)),
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=TraceState(),
    )
    context: Context = set_span_in_context(NonRecordingSpan(parent))
    tracer = trace.get_tracer("enterprise-data-copilot.agent")
    with tracer.start_as_current_span(
        f"agent.node.{node}",
        context=context,
        kind=SpanKind.INTERNAL,
        attributes={"agent.node": node},
    ) as span:
        yield span


def mark_span_error(span: Span, error: Exception, error_code: str) -> None:
    span.set_attribute("error.type", error_code)
    span.set_status(Status(StatusCode.ERROR, error_code))
    span.record_exception(error, attributes={"exception.escaped": True})


async def observe_http(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = getattr(request.scope.get("route"), "path", None) or _safe_route(request.url.path)
        method = request.method.upper()
        HTTP_REQUESTS.labels(method, route, str(status)).inc()
        HTTP_DURATION.labels(method, route).observe(max(0, perf_counter() - started))


def prometheus_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_model_tokens(
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> None:
    if input_tokens is not None:
        MODEL_TOKENS.labels(provider, model, "input").inc(input_tokens)
    if output_tokens is not None:
        MODEL_TOKENS.labels(provider, model, "output").inc(output_tokens)


def _safe_route(path: str) -> str:
    return _UUID.sub("{id}", path)[:160]
