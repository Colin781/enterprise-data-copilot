from app.agent.charting import build_chart_spec


def test_chart_spec_is_deterministic_and_closed() -> None:
    line = build_chart_spec(
        ["quarter", "revenue", "orders"],
        [{"quarter": "2025-Q1", "revenue": 12.5, "orders": 3}],
    )
    pie = build_chart_spec(
        ["category", "revenue"],
        [{"category": "Beverages", "revenue": 10}, {"category": "Seafood", "revenue": 8}],
    )
    decimal_strings = build_chart_spec(
        ["quarter_start", "total_sales"],
        [
            {"quarter_start": "2025-01-01", "total_sales": "4151.76000"},
            {"quarter_start": "2025-04-01", "total_sales": "4103.62600"},
        ],
    )
    table = build_chart_spec(["customer"], [{"customer": "ALFKI"}])

    assert line.model_dump() == {
        "type": "line",
        "title": "分析结果",
        "x": "quarter",
        "series": ("revenue", "orders"),
    }
    assert pie.type == "pie"
    assert decimal_strings.type == "line"
    assert decimal_strings.series == ("total_sales",)
    assert table.type == "table"
    assert "code" not in line.model_dump()
