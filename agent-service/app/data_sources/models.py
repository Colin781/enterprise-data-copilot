import re
from dataclasses import dataclass

from pydantic import SecretStr

from app.settings import BusinessDatabaseSettings

_IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class DataSourceConfig:
    source_id: str
    host: str
    port: int
    database: str
    username: str
    password: SecretStr
    allowed_schema: str
    connect_timeout_seconds: int = 3
    statement_timeout_ms: int = 2_000

    def __post_init__(self) -> None:
        if not _IDENTIFIER_PATTERN.fullmatch(self.allowed_schema):
            raise ValueError("allowed_schema must be a simple PostgreSQL identifier")
        if not 1 <= self.port <= 65_535:
            raise ValueError("port must be between 1 and 65535")
        if self.connect_timeout_seconds <= 0 or self.statement_timeout_ms <= 0:
            raise ValueError("database timeouts must be positive")

    @classmethod
    def from_settings(cls, settings: BusinessDatabaseSettings) -> "DataSourceConfig":
        return cls(
            source_id="northwind-demo",
            host=settings.host,
            port=settings.port,
            database=settings.name,
            username=settings.readonly_user,
            password=settings.readonly_password,
            allowed_schema=settings.allowed_schema,
            connect_timeout_seconds=settings.connect_timeout_seconds,
            statement_timeout_ms=settings.statement_timeout_ms,
        )

    def connection_parameters(self) -> dict[str, object]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.username,
            "password": self.password.get_secret_value(),
            "connect_timeout": self.connect_timeout_seconds,
            "options": f"-c statement_timeout={self.statement_timeout_ms}",
        }

    def __repr__(self) -> str:
        return (
            "DataSourceConfig("
            f"source_id={self.source_id!r}, host={self.host!r}, port={self.port!r}, "
            f"database={self.database!r}, username={self.username!r}, "
            "password=SecretStr('**********'), "
            f"allowed_schema={self.allowed_schema!r})"
        )


@dataclass(frozen=True, slots=True)
class ConnectionCheck:
    source_id: str
    database: str
    username: str
    transaction_read_only: bool
