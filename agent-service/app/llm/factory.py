import httpx

from app.llm.errors import LLMConfigurationError
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.llm.structured import StructuredLLMClient
from app.settings import LLMSettings, get_llm_settings


def create_structured_llm_client(
    settings: LLMSettings | None = None,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> StructuredLLMClient:
    resolved = settings or get_llm_settings()
    if resolved.provider == "openrouter" and not resolved.api_key.get_secret_value().strip():
        raise LLMConfigurationError()

    provider = OpenAICompatibleProvider(
        provider_name=resolved.provider,
        base_url=str(resolved.base_url),
        api_key=resolved.api_key,
        model=resolved.model,
        connect_timeout_seconds=resolved.connect_timeout_seconds,
        app_name=resolved.app_name,
        site_url=str(resolved.site_url) if resolved.site_url else None,
        client=http_client,
    )
    return StructuredLLMClient(
        provider,
        structured_output_mode=resolved.structured_output_mode,
        request_timeout_seconds=resolved.request_timeout_seconds,
        max_output_tokens=resolved.max_output_tokens,
        max_attempts=resolved.max_attempts,
        invalid_response_retries=resolved.invalid_response_retries,
        initial_backoff_seconds=resolved.initial_backoff_seconds,
        max_backoff_seconds=resolved.max_backoff_seconds,
    )
