"""Grounded, bounded descriptions of a SQL result; no causal inference."""

from decimal import Decimal, InvalidOperation
from typing import Any


def describe_sql_result(columns: list[str], rows: list[dict[str, Any]], *, truncated: bool) -> str:
    if not rows:
        answer = (
            "查询已执行，但结果在返回第一行前触及大小上限，无法判断是否有符合条件的数据。"
            if truncated
            else "查询已完成，但没有符合条件的数据。"
        )
    else:
        metric = next(
            (
                column
                for column in columns
                if not _dimension(column)
                and all(_number(row.get(column)) is not None for row in rows)
            ),
            None,
        )
        if metric is None:
            answer = f"查询返回 {len(rows)} 行。" + _first_row(columns, rows[0])
        elif len(rows) == 1:
            answer = (
                f"查询返回 1 行：{_label(columns, rows[0], metric)}"
                f"{metric}为 {_text(rows[0][metric])}。"
            )
        elif len(rows) <= 4:
            details = "；".join(
                f"{_label(columns, row, metric)}{metric}为 {_text(row[metric])}" for row in rows
            )
            answer = f"查询返回 {len(rows)} 行：{details}。"
        else:
            highest = max(rows, key=lambda row: _number(row[metric]) or Decimal(0))
            lowest = min(rows, key=lambda row: _number(row[metric]) or Decimal(0))
            answer = (
                f"查询返回 {len(rows)} 行。在已返回数据中，{metric}最高的是"
                f"{_label(columns, highest, metric)}{_text(highest[metric])}，最低的是"
                f"{_label(columns, lowest, metric)}{_text(lowest[metric])}。"
            )
        if metric is not None and len(rows) > 1:
            answer += _period_change(columns, rows, metric)
    if truncated and rows:
        answer += f"结果已截断，上述描述仅基于返回的 {len(rows)} 行，不代表完整结果。"
    return answer


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _dimension(column: str) -> bool:
    name = column.lower()
    return any(
        marker in name
        for marker in (
            "_id",
            "id_",
            "year",
            "month",
            "quarter",
            "date",
            "time",
            "rank",
            "年份",
            "月份",
            "季度",
            "日期",
        )
    )


def _text(value: Any) -> str:
    return " ".join(str(value).split())[:80]


def _label(columns: list[str], row: dict[str, Any], metric: str) -> str:
    dimensions = [f"{column}={_text(row.get(column))}" for column in columns if column != metric]
    return "、".join(dimensions[:2]) + "的" if dimensions else ""


def _first_row(columns: list[str], row: dict[str, Any]) -> str:
    fields = "、".join(f"{column}={_text(row.get(column))}" for column in columns[:3])
    return f"首行：{fields}。" if fields else ""


def _period_change(columns: list[str], rows: list[dict[str, Any]], metric: str) -> str:
    periods = [
        column
        for column in columns
        if any(
            marker in column.lower()
            for marker in ("year", "month", "quarter", "date", "年份", "月份", "季度", "日期")
        )
    ]
    if not periods:
        return ""
    keys = [tuple(str(row.get(column, "")) for column in periods) for row in rows]
    if keys != sorted(keys) or keys[0] == keys[-1]:
        return ""
    first = _number(rows[0][metric])
    last = _number(rows[-1][metric])
    if first is None or last is None:
        return ""
    change = last - first
    direction = "增长" if change > 0 else "下降" if change < 0 else "持平"
    absolute = format(abs(change).normalize(), "f")
    relative = f"，约 {abs(change / first * 100):.2f}%" if first else ""
    return f"从首期到末期，{metric}{direction} {absolute}{relative}（仅比较返回的首末期）。"
