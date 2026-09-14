class NL2SQLError(RuntimeError):
    code = "NL2SQL_ERROR"
    public_message = "The analysis query could not be produced safely."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class NL2SQLPolicyError(NL2SQLError):
    code = "NL2SQL_QUESTION_REJECTED"
    public_message = "The request is outside the read-only analytics policy."

    def __init__(self, reason_code: str) -> None:
        super().__init__()
        self.reason_code = reason_code


class SchemaSelectionError(NL2SQLError):
    code = "NL2SQL_SCHEMA_SELECTION_FAILED"
    public_message = "The model selected an invalid set of database tables."


class NL2SQLRepairExhaustedError(NL2SQLError):
    code = "NL2SQL_REPAIR_EXHAUSTED"
    public_message = "The SQL could not be repaired within the configured attempt limit."

    def __init__(self, last_error_code: str) -> None:
        super().__init__()
        self.last_error_code = last_error_code
