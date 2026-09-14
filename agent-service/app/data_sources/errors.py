class DataSourceError(RuntimeError):
    """A safe data source failure whose text can cross the service boundary."""

    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


class DataSourceUnavailableError(DataSourceError):
    def __init__(self) -> None:
        super().__init__(
            code="DATA_SOURCE_UNAVAILABLE",
            public_message="The configured business data source is unavailable.",
        )


class DataSourcePermissionError(DataSourceError):
    def __init__(self) -> None:
        super().__init__(
            code="DATA_SOURCE_PERMISSION_DENIED",
            public_message="The business data source rejected the read-only connection.",
        )
