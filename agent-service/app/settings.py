from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGENT_",
        extra="ignore",
    )

    service_name: str = "agent-service"
    environment: str = "development"
    version: str = "0.1.0"


class BusinessDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BUSINESS_DB_",
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 5433
    name: str = "northwind"
    readonly_user: str = "northwind_reader"
    readonly_password: SecretStr = Field(default=SecretStr("change-me-business-reader"))
    allowed_schema: str = "northwind"
    connect_timeout_seconds: int = 3
    statement_timeout_ms: int = 2_000
    metadata_cache_ttl_seconds: int = 300


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LLM_",
        extra="ignore",
    )

    provider: Literal["openrouter", "openai-compatible"] = "openrouter"
    base_url: AnyHttpUrl = AnyHttpUrl("https://openrouter.ai/api/v1")
    api_key: SecretStr = Field(default=SecretStr(""))
    model: str = Field(default="openai/gpt-4.1-mini", min_length=1, max_length=200)
    structured_output_mode: Literal["json_schema", "json_object"] = "json_schema"
    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    max_output_tokens: int = Field(default=2_000, ge=1, le=32_768)
    max_attempts: int = Field(default=3, ge=1, le=5)
    invalid_response_retries: int = Field(default=1, ge=0, le=1)
    initial_backoff_seconds: float = Field(default=0.25, ge=0, le=10)
    max_backoff_seconds: float = Field(default=2.0, ge=0, le=30)
    app_name: str | None = Field(default="Enterprise Data Copilot", max_length=100)
    site_url: AnyHttpUrl | None = None


class QuerySafetySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="QUERY_SAFETY_",
        extra="ignore",
    )

    max_rows: int = Field(default=100, ge=1, le=10_000)
    max_columns: int = Field(default=50, ge=1, le=500)
    max_result_bytes: int = Field(default=1_000_000, ge=64, le=10_000_000)
    max_total_cost: float = Field(default=10_000, gt=0)
    max_plan_rows: int = Field(default=100_000, ge=1)


class NL2SQLSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NL2SQL_",
        extra="ignore",
    )

    max_selected_tables: int = Field(default=6, ge=1, le=6)
    max_repairs: int = Field(default=2, ge=0, le=2)


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_business_database_settings() -> BusinessDatabaseSettings:
    return BusinessDatabaseSettings()


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


@lru_cache
def get_query_safety_settings() -> QuerySafetySettings:
    return QuerySafetySettings()


@lru_cache
def get_nl2sql_settings() -> NL2SQLSettings:
    return NL2SQLSettings()
