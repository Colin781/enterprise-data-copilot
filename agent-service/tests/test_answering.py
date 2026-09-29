from app.agent.answering import describe_sql_result


def test_quarterly_values_are_described_without_inventing_a_cause() -> None:
    answer = describe_sql_result(
        ["quarter", "sales"],
        [
            {"quarter": "Q1", "sales": "100.00"},
            {"quarter": "Q2", "sales": "120.00"},
            {"quarter": "Q3", "sales": "80.00"},
            {"quarter": "Q4", "sales": "150.00"},
        ],
        truncated=False,
    )
    assert "Q1的sales为 100.00" in answer
    assert "Q4的sales为 150.00" in answer
    assert "从首期到末期，sales增长 50，约 50.00%" in answer
    assert "原因" not in answer


def test_unsorted_periods_are_not_described_as_a_trend() -> None:
    answer = describe_sql_result(
        ["quarter", "sales"],
        [{"quarter": "Q2", "sales": "120"}, {"quarter": "Q1", "sales": "100"}],
        truncated=False,
    )
    assert "从首期到末期" not in answer


def test_truncation_qualifies_answer_even_below_row_limit() -> None:
    answer = describe_sql_result(
        ["customer", "sales"],
        [{"customer": "Acme", "sales": "9.99"}],
        truncated=True,
    )
    assert "Acme的sales为 9.99" in answer
    assert "结果已截断" in answer
    assert "仅基于返回的 1 行" in answer


def test_empty_and_non_numeric_results_remain_grounded() -> None:
    assert "没有符合条件的数据" in describe_sql_result(["name"], [], truncated=False)
    assert "首行：name=Acme" in describe_sql_result(
        ["name"], [{"name": "Acme"}, {"name": "Beta"}], truncated=False
    )
    assert "无法判断是否有符合条件的数据" in describe_sql_result(["name"], [], truncated=True)
