import hashlib

from sqlglot import exp, parse
from sqlglot.errors import ParseError, TokenError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import OptimizeError

from app.query_safety.errors import SQLPolicyViolationError
from app.query_safety.models import GuardedQuery, QueryPolicy

_FORBIDDEN_FUNCTIONS = frozenset(
    {
        "dblink",
        "dblink_exec",
        "lo_export",
        "lo_import",
        "nextval",
        "pg_ls_dir",
        "pg_read_binary_file",
        "pg_read_file",
        "pg_sleep",
        "set_config",
        "setval",
    }
)
_FORBIDDEN_NODES = (
    exp.DDL,
    exp.DML,
    exp.Command,
    exp.Copy,
    exp.Into,
    exp.Lock,
    exp.Transaction,
)


class SQLGuard:
    def inspect(self, query: str, policy: QueryPolicy) -> GuardedQuery:
        if not query.strip():
            raise SQLPolicyViolationError("EMPTY_QUERY")

        try:
            statements = parse(query, read="postgres")
        except (ParseError, TokenError):
            raise SQLPolicyViolationError("SQL_PARSE_ERROR") from None

        if len(statements) != 1:
            raise SQLPolicyViolationError("MULTIPLE_STATEMENTS")

        statement = statements[0]
        if statement is None or not isinstance(statement, exp.Query):
            raise SQLPolicyViolationError("NON_READ_ONLY_STATEMENT")
        if any(statement.find(node_type) is not None for node_type in _FORBIDDEN_NODES):
            raise SQLPolicyViolationError("FORBIDDEN_SQL_OPERATION")

        self._check_functions(statement)
        self._check_query_shape(statement)
        tables = self._check_tables(statement, policy)
        statement = self._qualify_columns(statement, policy)
        normalized_sql = statement.sql(dialect="postgres", pretty=False)
        bounded_sql = (
            f"SELECT * FROM ({normalized_sql}) AS _copilot_bounded LIMIT {policy.max_rows + 1}"
        )
        return GuardedQuery(
            normalized_sql=normalized_sql,
            bounded_sql=bounded_sql,
            query_fingerprint=fingerprint_query(normalized_sql),
            referenced_tables=tuple(sorted(tables)),
            row_fetch_limit=policy.max_rows + 1,
        )

    @staticmethod
    def _check_functions(statement: exp.Query) -> None:
        for function in statement.find_all(exp.Func):
            name = function.name if isinstance(function, exp.Anonymous) else function.sql_name()
            normalized_name = name.lower()
            if normalized_name in _FORBIDDEN_FUNCTIONS:
                raise SQLPolicyViolationError("FORBIDDEN_FUNCTION")
            if isinstance(function, exp.Anonymous):
                raise SQLPolicyViolationError("FUNCTION_NOT_ALLOWED")

    @staticmethod
    def _check_tables(statement: exp.Query, policy: QueryPolicy) -> set[str]:
        cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
        referenced_tables: set[str] = set()
        for table in statement.find_all(exp.Table):
            table_name = table.name
            schema_name = table.db
            if not schema_name and table_name.lower() in cte_names:
                continue
            if table.catalog or (schema_name and schema_name != policy.allowed_schema):
                raise SQLPolicyViolationError("CROSS_SCHEMA_REFERENCE")
            if table_name not in policy.allowed_tables:
                raise SQLPolicyViolationError("TABLE_NOT_ALLOWED")
            referenced_tables.add(f"{policy.allowed_schema}.{table_name}")
        return referenced_tables

    @staticmethod
    def _check_query_shape(statement: exp.Query) -> None:
        with_clause = statement.args.get("with_")
        if with_clause is not None and with_clause.args.get("recursive"):
            raise SQLPolicyViolationError("RECURSIVE_QUERY_NOT_ALLOWED")

        for join in statement.find_all(exp.Join):
            is_cross = str(join.args.get("kind") or "").upper() == "CROSS"
            has_condition = join.args.get("on") is not None or join.args.get("using") is not None
            condition_is_true = isinstance(join.args.get("on"), exp.Boolean) and bool(
                join.args["on"].this
            )
            if is_cross or not has_condition or condition_is_true:
                raise SQLPolicyViolationError("CARTESIAN_JOIN_NOT_ALLOWED")

    @staticmethod
    def _qualify_columns(statement: exp.Query, policy: QueryPolicy) -> exp.Query:
        if not policy.allowed_columns:
            return statement

        schema = {
            policy.allowed_schema: {
                table: {column: "unknown" for column in columns}
                for table, columns in policy.allowed_columns.items()
            }
        }
        try:
            qualified = qualify(
                statement,
                dialect="postgres",
                schema=schema,
                validate_qualify_columns=True,
                quote_identifiers=False,
                identify=False,
            )
        except OptimizeError:
            raise SQLPolicyViolationError("COLUMN_NOT_ALLOWED") from None
        if not isinstance(qualified, exp.Query):
            raise SQLPolicyViolationError("NON_READ_ONLY_STATEMENT")
        return qualified


def fingerprint_query(query: str) -> str:
    return f"sha256:{hashlib.sha256(query.encode()).hexdigest()}"
