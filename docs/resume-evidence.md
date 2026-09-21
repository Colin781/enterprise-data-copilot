# 简历证据与可追溯表述

以下数字只能在对应报告和 CI 仍可复现时使用。

## 可使用的项目描述

- 独立实现 Spring Boot + FastAPI + LangGraph 企业数据 Copilot，以 Java 管理多租户、RBAC、任务、审批、审计和 SSE，以 Python 管理混合检索、安全 NL2SQL 和只读执行。
- 建立 55 条 Northwind NL2SQL、20 条危险问题和 24 条 RAG 评测集；离线 Gold Replay 的 execution accuracy、安全查询通过率和危险请求阻断率均为 100%，真实模型准确率未混入该数字。
- 使用 PostgreSQL FTS、向量检索与加权 RRF；当前固定数据集 lexical/vector/hybrid Recall@5 均为 1.0，vector MRR 0.885，hybrid MRR 1.0。
- 用 SQLGlot AST、表/字段 allowlist、EXPLAIN 成本、只读事务、statement timeout 和行/列/字节上限构建多层防护；20 条危险问题全部在执行前阻断。
- 通过 W3C Trace Context、OpenTelemetry 节点 span、Micrometer/Prometheus 指标和 k6 场景建立跨服务诊断与性能证据。

## 证据位置

| 声明 | 证据 |
|---|---|
| P10 数据量与准确率 | `evaluation/northwind/p10-offline-baseline.json` |
| RAG 对比 | `evaluation/northwind/p6-rag-baseline.json` 与 P10 报告 |
| P11 本地性能 | `evaluation/p11-local-performance.json` |
| Java/Python/Web 自动化 | `.github/workflows/ci.yml` 与 `make verify-all` |
| 安全设计 | `docs/adr/`、P2/P5/P7/P11 阶段文档 |

不要声称已经有公网用户、云端 SLA、真实模型 100% accuracy、生产规模吞吐或尚未发布的在线 Demo。
