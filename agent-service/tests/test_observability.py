import pytest

from app.observability import normalize_trace_id, trace_id_from_traceparent
from app.settings import ObservabilitySettings


def test_valid_w3c_traceparent_extracts_the_shared_trace_id() -> None:
    trace_id = "0123456789abcdef0123456789abcdef"

    assert trace_id_from_traceparent(f"00-{trace_id}-0123456789abcdef-01") == trace_id


@pytest.mark.parametrize(
    "value",
    (
        "bad",
        "00-00000000000000000000000000000000-0123456789abcdef-01",
        "00-0123456789abcdef0123456789abcdef-0000000000000000-01",
        "01-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
    ),
)
def test_invalid_w3c_traceparent_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        trace_id_from_traceparent(value)


def test_legacy_trace_value_is_deterministically_normalized_without_logging_it() -> None:
    first = normalize_trace_id("legacy-trace-id-123456")

    assert first == normalize_trace_id("legacy-trace-id-123456")
    assert len(first) == 32
    assert first != normalize_trace_id("different-legacy-value")


def test_empty_otlp_endpoint_disables_export_without_failing_startup() -> None:
    settings = ObservabilitySettings(otlp_http_endpoint="")  # type: ignore[arg-type]

    assert settings.otlp_http_endpoint is None
