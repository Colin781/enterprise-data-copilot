from collections.abc import Sequence

from app.data_sources.models import DataSourceConfig
from app.llm.models import LLMMessage, LLMTokenUsage
from app.llm.structured import StructuredLLMClient
from app.metadata.models import SchemaSnapshot
from app.nl2sql.errors import NL2SQLRepairExhaustedError, SchemaSelectionError
from app.nl2sql.models import NL2SQLDraft, NL2SQLResult, TableSelection
from app.nl2sql.prompts import generation_messages, repair_messages, selection_messages
from app.nl2sql.question_guard import QuestionGuard
from app.nl2sql.table_references import normalize_reported_tables
from app.query_safety.errors import QueryApprovalRequiredError, QuerySafetyError
from app.query_safety.models import QueryContext, QueryPolicy
from app.query_safety.service import SafeQueryService


class NL2SQLService:
    def __init__(
        self,
        *,
        llm_client: StructuredLLMClient,
        safe_query_service: SafeQueryService,
        question_guard: QuestionGuard | None = None,
        max_selected_tables: int = 6,
        max_repairs: int = 2,
    ) -> None:
        if not 1 <= max_selected_tables <= 6:
            raise ValueError("max_selected_tables must be between 1 and 6")
        if not 0 <= max_repairs <= 2:
            raise ValueError("max_repairs must be between 0 and 2")
        self._llm_client = llm_client
        self._safe_query_service = safe_query_service
        self._question_guard = question_guard or QuestionGuard()
        self._max_selected_tables = max_selected_tables
        self._max_repairs = max_repairs

    async def answer(
        self,
        *,
        question: str,
        snapshot: SchemaSnapshot,
        config: DataSourceConfig,
        context: QueryContext,
        policy: QueryPolicy,
    ) -> NL2SQLResult:
        safe_question = self._question_guard.inspect(question)
        selection_result = await self._llm_client.generate(
            messages=_messages(selection_messages(safe_question, snapshot)),
            response_model=TableSelection,
        )
        selected_tables = self._validate_selection(selection_result.output, snapshot, policy)
        selected_policy = policy.restrict_to_tables(frozenset(selected_tables))
        base_messages = generation_messages(
            safe_question, snapshot, selected_tables, selected_policy
        )
        messages = base_messages
        repair_count = 0
        model_calls = selection_result.attempts
        usage = selection_result.usage

        while True:
            draft_result = await self._llm_client.generate(
                messages=_messages(messages),
                response_model=NL2SQLDraft,
            )
            model_calls += draft_result.attempts
            usage = _add_usage(usage, draft_result.usage)
            self._validate_draft_tables(
                draft_result.output,
                selected_tables,
                allowed_schema=policy.allowed_schema,
            )
            try:
                outcome = self._safe_query_service.execute_generated(
                    sql=draft_result.output.sql,
                    context=context,
                    config=config,
                    policy=selected_policy,
                )
            except QueryApprovalRequiredError:
                raise
            except QuerySafetyError as error:
                if repair_count >= self._max_repairs:
                    raise NL2SQLRepairExhaustedError(_safe_error_code(error)) from error
                repair_count += 1
                messages = repair_messages(
                    base_messages,
                    previous_sql=draft_result.output.sql,
                    safe_error_code=_safe_error_code(error),
                )
                continue

            return NL2SQLResult(
                analysis_plan=draft_result.output.analysis_plan,
                selected_tables=selected_tables,
                sql=draft_result.output.sql,
                repair_count=repair_count,
                model_calls=model_calls,
                provider=draft_result.provider,
                model=draft_result.model,
                usage=usage,
                outcome=outcome,
            )

    def _validate_selection(
        self,
        selection: TableSelection,
        snapshot: SchemaSnapshot,
        policy: QueryPolicy,
    ) -> tuple[str, ...]:
        tables = tuple(dict.fromkeys(selection.tables))
        known_tables = {table.name for table in snapshot.tables}
        if (
            len(tables) != len(selection.tables)
            or len(tables) > self._max_selected_tables
            or not set(tables).issubset(known_tables & policy.allowed_tables)
        ):
            raise SchemaSelectionError()
        return tables

    @staticmethod
    def _validate_draft_tables(
        draft: NL2SQLDraft,
        selected_tables: tuple[str, ...],
        *,
        allowed_schema: str,
    ) -> None:
        reported_tables = normalize_reported_tables(
            draft.tables_used, allowed_schema=allowed_schema
        )
        if not set(reported_tables).issubset(selected_tables):
            raise SchemaSelectionError()


def _messages(items: Sequence[tuple[str, str]]) -> tuple[LLMMessage, ...]:
    return tuple(LLMMessage(role=role, content=content) for role, content in items)  # type: ignore[arg-type]


def _safe_error_code(error: QuerySafetyError) -> str:
    reason_code = getattr(error, "reason_code", None)
    return str(reason_code or error.code)


def _add_usage(left: LLMTokenUsage, right: LLMTokenUsage) -> LLMTokenUsage:
    def add(first: int | None, second: int | None) -> int | None:
        if first is None and second is None:
            return None
        return (first or 0) + (second or 0)

    return LLMTokenUsage(
        input_tokens=add(left.input_tokens, right.input_tokens),
        output_tokens=add(left.output_tokens, right.output_tokens),
        total_tokens=add(left.total_tokens, right.total_tokens),
    )
