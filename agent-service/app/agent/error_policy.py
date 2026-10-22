"""Redacted error classification shared by node traces and debugging tools."""

import httpx

from app.llm.errors import LLMError


def classify_error(error: Exception) -> dict:
    if isinstance(error, LLMError):
        return {"category": "model", "retryable": error.retryable}
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        return {"category": "timeout", "retryable": True}
    if isinstance(error, httpx.TransportError):
        return {"category": "transport", "retryable": True}
    if isinstance(error, (ValueError, TypeError)):
        return {"category": "validation", "retryable": False}
    code = getattr(error, "code", "")
    if "POLICY" in code or "REJECT" in code:
        return {"category": "policy", "retryable": False}
    if "STORE" in code:
        return {"category": "storage", "retryable": False}
    return {"category": "internal", "retryable": False}
