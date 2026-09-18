class RetrievalError(Exception):
    code = "RETRIEVAL_FAILED"
    public_message = "Metric knowledge could not be processed."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(self.public_message)


class DocumentParseError(RetrievalError):
    code = "DOCUMENT_INVALID"
    public_message = "The metric document is empty, unsupported, or malformed."


class DocumentLimitError(RetrievalError):
    code = "DOCUMENT_LIMIT_EXCEEDED"
    public_message = "The metric document exceeds an ingestion limit."


class RetrievalStoreError(RetrievalError):
    code = "RETRIEVAL_STORE_UNAVAILABLE"
    public_message = "The metric knowledge store is unavailable."
