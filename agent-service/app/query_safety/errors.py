class QuerySafetyError(RuntimeError):
    code = "QUERY_SAFETY_ERROR"
    public_message = "The query could not be processed safely."

    def __init__(self) -> None:
        super().__init__(self.public_message)


class SQLPolicyViolationError(QuerySafetyError):
    code = "SQL_POLICY_VIOLATION"
    public_message = "The SQL query was rejected by the read-only policy."

    def __init__(self, reason_code: str) -> None:
        super().__init__()
        self.reason_code = reason_code


class QueryTimeoutError(QuerySafetyError):
    code = "QUERY_TIMEOUT"
    public_message = "The read-only query exceeded its time limit."


class QueryPermissionError(QuerySafetyError):
    code = "QUERY_PERMISSION_DENIED"
    public_message = "The business database rejected the read-only query."


class QueryExecutionError(QuerySafetyError):
    code = "QUERY_EXECUTION_FAILED"
    public_message = "The read-only query could not be executed."


class QueryResultLimitError(QuerySafetyError):
    code = "QUERY_RESULT_LIMIT_EXCEEDED"
    public_message = "The query result exceeded a configured safety limit."


class QueryAuditError(QuerySafetyError):
    code = "QUERY_AUDIT_FAILED"
    public_message = "The query audit event could not be recorded."


class QueryApprovalRequiredError(QuerySafetyError):
    code = "QUERY_APPROVAL_REQUIRED"
    public_message = "The query exceeds the automatic execution cost policy."

    def __init__(
        self,
        reason_code: str,
        *,
        estimated_total_cost: float,
        estimated_plan_rows: int,
    ) -> None:
        super().__init__()
        self.reason_code = reason_code
        self.estimated_total_cost = estimated_total_cost
        self.estimated_plan_rows = estimated_plan_rows
