#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "docker-compose.full.yml",
    "platform-api/Dockerfile",
    "agent-service/Dockerfile",
    "web/Dockerfile",
    "performance/k6/p11-platform-and-sse.js",
    "docs/stage-11-observability-deployment.md",
    "docs/stage-12-portfolio-handoff.md",
    "docs/demo-script.md",
    "docs/resume-evidence.md",
    "docs/adr/0001-java-python-boundary.md",
    "docs/adr/0002-no-arbitrary-code-execution.md",
    "docs/adr/0003-hybrid-metric-retrieval.md",
    "evaluation/northwind/p10-offline-baseline.json",
    "evaluation/p11-local-performance.json",
)


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"missing portfolio evidence: {', '.join(missing)}")

    report = json.loads(
        (ROOT / "evaluation/northwind/p10-offline-baseline.json").read_text(encoding="utf-8")
    )
    metrics = report["metrics"]
    assert report["evaluation_mode"] == "scripted_gold_replay"
    assert report["real_model_evaluation"] is False
    assert metrics["nl2sql_cases"] >= 50
    assert metrics["dangerous_cases"] >= 20
    assert report["rag"]["cases"] >= 20

    performance = json.loads(
        (ROOT / "evaluation/p11-local-performance.json").read_text(encoding="utf-8")
    )
    assert performance["scenario"]["external_model_calls"] == 0
    assert performance["scenario"]["completed_iterations"] > 0
    assert performance["thresholds"]["passed"] is True

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in (
        "## 30 秒介绍",
        "## 架构与请求时序",
        "## 安全边界",
        "## 可复现评测",
        "## 三个演示问题",
        "## 已知限制",
        "## 灵感与独立实现声明",
    ):
        if heading not in readme:
            raise SystemExit(f"README is missing required section: {heading}")

    print(
        "P12 evidence verified: "
        f"{metrics['nl2sql_cases']} NL2SQL, "
        f"{metrics['dangerous_cases']} dangerous, {report['rag']['cases']} RAG cases"
    )


if __name__ == "__main__":
    main()
