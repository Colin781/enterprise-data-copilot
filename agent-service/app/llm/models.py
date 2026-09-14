from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=50_000, repr=False)


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    messages: tuple[LLMMessage, ...] = Field(min_length=1, repr=False)
    response_schema: dict[str, Any] = Field(repr=False)
    schema_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    structured_output_mode: Literal["json_schema", "json_object"] = "json_schema"
    max_output_tokens: int = Field(ge=1, le=32_768)
    timeout_seconds: float = Field(gt=0, le=300)


class LLMTokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class LLMCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1, repr=False)
    model: str
    request_id: str | None = None
    usage: LLMTokenUsage = Field(default_factory=LLMTokenUsage)


class StructuredLLMResult[StructuredOutputT: BaseModel](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    output: StructuredOutputT
    provider: str
    model: str
    request_id: str | None = None
    attempts: int = Field(ge=1)
    usage: LLMTokenUsage = Field(default_factory=LLMTokenUsage)
