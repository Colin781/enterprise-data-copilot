from collections.abc import Sequence


class LLMError(RuntimeError):
    code = "LLM_ERROR"
    retryable = False
    public_message = "The language model request failed."

    def __init__(self, *, validation_issues: Sequence[str] = ()) -> None:
        super().__init__(self.public_message)
        self.validation_issues = tuple(validation_issues)


class LLMConfigurationError(LLMError):
    code = "LLM_CONFIGURATION_ERROR"
    public_message = "The language model provider is not configured."


class LLMAuthenticationError(LLMError):
    code = "LLM_AUTHENTICATION_ERROR"
    public_message = "The language model provider rejected its credentials."


class LLMRequestRejectedError(LLMError):
    code = "LLM_REQUEST_REJECTED"
    public_message = "The language model provider rejected the request."


class LLMRateLimitError(LLMError):
    code = "LLM_RATE_LIMITED"
    retryable = True
    public_message = "The language model provider is temporarily rate limited."


class LLMTimeoutError(LLMError):
    code = "LLM_TIMEOUT"
    retryable = True
    public_message = "The language model request timed out."


class LLMUnavailableError(LLMError):
    code = "LLM_UNAVAILABLE"
    retryable = True
    public_message = "The language model provider is temporarily unavailable."


class LLMInvalidResponseError(LLMError):
    code = "LLM_INVALID_RESPONSE"
    retryable = True
    public_message = "The language model returned an invalid structured response."
