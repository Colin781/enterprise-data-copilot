from pathlib import Path

import yaml
from openapi_spec_validator import validate

from app.agent.demo import demo


def test_intelligence_contract_is_valid_openapi():
    document = Path(__file__).parents[2] / "contracts/openapi-intelligence.yaml"
    validate(yaml.safe_load(document.read_text(encoding="utf-8")))


def test_repair_approval_and_checkpoint_replay_demo():
    report = demo()
    assert report["runs"][0]["attempts"] == 2
    assert all(run["sql_executions"] == 1 for run in report["runs"])
    assert all(
        event["status"] != "FAILED" for run in report["runs"] for event in run["node_events"]
    )
