import json
from pathlib import Path


def test_initial_gold_set_has_fifteen_well_formed_cases() -> None:
    path = Path(__file__).parents[2] / "evaluation/northwind/gold-v1.jsonl"
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    assert len(cases) == 15
    assert len({case["id"] for case in cases}) == 15
    assert all(case["question"] for case in cases)
    assert all(case["gold_sql"].lstrip().upper().startswith(("SELECT", "WITH")) for case in cases)
    assert all(case["expected_columns"] for case in cases)
    assert all(case["tags"] for case in cases)
    assert all("restricted" not in case["gold_sql"].lower() for case in cases)
