from decimal import Decimal, InvalidOperation
from numbers import Number
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChartSpec(BaseModel):
    """A closed, data-only chart contract; it never contains executable code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["bar", "line", "pie", "table"]
    title: str = Field(min_length=1, max_length=160)
    x: str | None = Field(default=None, max_length=160)
    series: tuple[str, ...] = Field(default=(), max_length=3)


def build_chart_spec(columns: list[str], rows: list[dict[str, Any]]) -> ChartSpec:
    if len(columns) < 2 or not rows:
        return ChartSpec(type="table", title="查询结果")

    x = columns[0]
    numeric = [
        column for column in columns[1:] if any(_is_number(row.get(column)) for row in rows[:50])
    ][:3]
    if not numeric:
        return ChartSpec(type="table", title="查询结果")

    normalized_x = x.lower()
    if any(
        marker in normalized_x
        for marker in ("date", "time", "month", "year", "quarter", "日期", "月份", "季度")
    ):
        chart_type = "line"
    elif len(rows) <= 8 and len(numeric) == 1:
        chart_type = "pie"
    else:
        chart_type = "bar"
    return ChartSpec(type=chart_type, title="分析结果", x=x, series=tuple(numeric))


def _is_number(value: Any) -> bool:
    if isinstance(value, Number) and not isinstance(value, bool):
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return Decimal(value).is_finite()
    except InvalidOperation:
        return False
