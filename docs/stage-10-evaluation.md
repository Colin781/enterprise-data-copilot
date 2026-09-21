# P10 完整自动化与评测验收记录

## 本阶段目标

把 P2～P9 分散的测试证据收敛为一个可重复运行、可区分真实模型与离线回放、能够输出失败分类的评测系统。P10 不把 gold SQL 回放结果包装成模型准确率，也不把顺序评测延迟包装成 P11 的并发性能指标。

## 评测资产

| 资产 | 数量 | 作用 |
|---|---:|---|
| `evaluation/northwind/nl2sql-gold-v2.jsonl` | 55 | 覆盖筛选、连接、聚合、日期、CTE、Top N、库存、折扣、员工、供应商和运输分析 |
| `evaluation/northwind/dangerous-questions-v1.jsonl` | 20 | 覆盖写操作、DDL、COPY、提示注入、密钥、跨租户、敏感字段和任意代码请求 |
| `evaluation/northwind/rag-gold-v1.jsonl` | 24 | 20 条可回答问题和 4 条应拒答问题，比较 lexical/vector/hybrid |
| `evaluation/northwind/p10-offline-baseline.json` | 1 | 保存逐案例结果、汇总指标、失败分类和限制声明 |

所有 NL2SQL gold case 均由 Pydantic 校验，并通过生产 `SQLGuard`。候选 SQL 与 gold SQL 都在固定 `northwind-compact-v1` PostgreSQL 中执行，比较规范化列名与执行结果，而不是比较 SQL 字符串。

## 实现内容

1. `app.evaluation.datasets` 负责 JSONL 解析、逐行错误定位和重复 ID 拒绝。
2. `app.evaluation.models` 定义数据集、逐案例结果、汇总指标和报告版本。
3. `app.evaluation.runner` 统一执行 NL2SQL、安全问题和 RAG 评测，记录延迟、Token、费用与失败分类。
4. `app.evaluation.cli` 提供 `scripted_gold_replay` 和 `configured_model` 两种明确分离的模式。
5. `make verify-p10` 运行 Python 单元/数据库集成测试和 Java WireMock 故障测试。
6. `make p10-eval` 生成离线基线；`make p10-eval-real` 必须显式指定，才会调用当前配置的外部模型。
7. Java Agent HTTP 客户端增加连接超时、请求超时和 `AGENT_INVALID_RESPONSE` 协议错误，WireMock 覆盖成功、超时、HTTP 500、非法 JSON 和缺字段响应。
8. CI 基础设施任务在固定数据库启动后运行 `make verify-p10`。

## 指标定义

| 指标 | 定义 |
|---|---|
| Execution accuracy | 候选 SQL 与 gold SQL 的真实执行列和行完全一致的比例 |
| Safe-query pass rate | 正常问题通过确定性安全规则并完成只读执行的比例 |
| Dangerous-query block rate | 危险问题在模型和数据库执行前被问题策略阻断，且原因码符合预期的比例 |
| End-to-end success rate | 正常问题完成安全执行且结果正确的比例 |
| First-generation success rate | 正常问题无需 SQL 修复即得到正确结果的比例 |
| Repaired success rate | 发生过修复的案例中最终正确的比例；未发生修复时为 `null` |
| Mean/P95 latency | 当前顺序评测中每个正常案例的墙钟耗时，不是并发压测指标 |
| Average tokens/cost | 仅统计供应商实际返回的 Token；费用只有显式提供单价时才计算 |
| Failure taxonomy | `dataset/model/schema_selection/safety/execution/result_mismatch/unknown` 分类及稳定错误码计数 |

## 两种评测模式

### 离线 gold 回放

`scripted_gold_replay` 用 Fake LLM 返回数据集中的 gold SQL，然后仍然经过生产选表约束、SQL guard、EXPLAIN 成本检查、只读账号和真实 PostgreSQL 执行。它证明的是：

- 55 条数据集 SQL 可执行且结果基准有效；
- 评测器确实按执行结果比较；
- 安全与审计链路不会被评测器绕过；
- 报告生成和失败分类可在 CI 中复现。

它不证明模型能从自然语言生成这些 SQL，因此报告固定包含：

```json
{"evaluation_mode":"scripted_gold_replay","real_model_evaluation":false}
```

### 配置模型评测

`configured_model` 使用 `.env` 中的 LLM provider/model，每题至少进行选表和 SQL 生成两次调用。CLI 必须同时给出 `--allow-external-model`，Makefile 将其封装为：

```bash
make p10-eval-real
```

该命令会把评测问题和 Northwind schema 发送给当前配置的模型服务。它不会自动切换模型源；更换供应商仍需人工决定。模型单价不是稳定配置，只有调用者显式提供输入/输出单价时才估算费用。

## 2026-09-18 本地离线结果

| 指标 | 结果 | 解释 |
|---|---:|---|
| NL2SQL cases | 55 | 达到收敛路线 50+ 要求 |
| Dangerous cases | 20 | 全部在模型/数据库前阻断 |
| Execution accuracy | 1.0000 | gold 回放管线基线，不是真实模型准确率 |
| Safe-query pass rate | 1.0000 | 55 条均通过生产 guard 和只读执行 |
| Dangerous-query block rate | 1.0000 | 原因码全部匹配 |
| End-to-end success rate | 1.0000 | 指离线回放的正常问题 |
| First-generation success rate | 1.0000 | 回放不触发修复 |
| Repaired success rate | `null` | 本基线没有修复样本，不虚构百分比 |
| Mean latency | 21.273 ms | 本机顺序回放，仅用于本次报告 |
| P95 latency | 27 ms | 本机顺序回放，不替代 P11 压测 |
| Average tokens/cost | `null` | Fake LLM 不产生供应商用量 |

RAG 共 24 条：lexical Recall@5/MRR 为 1.0/1.0，vector 为 1.0/0.885，hybrid 为 1.0/1.0；三种模式引用命中率和拒答正确率均为 1.0。向量结果仍是 deterministic-hashing-64 管线基线，不代表托管 embedding 模型质量。

## 验收命令

```bash
make compose-up
make verify-p10
make p10-eval
```

本地实测：

- P10 Python 数据集、guard、危险问题和指标计算：24 passed；
- P10 真实 PostgreSQL 联合评测：1 passed，内部执行并比较 55 个候选结果与 55 个 gold 结果；
- Java WireMock Agent HTTP 边界：5 passed；
- 报告未包含 SQL、数据库凭据、模型密钥或业务结果明细。

## 后续边界

- 真实模型批量报告尚未运行，因此不能声称真实模型 execution accuracy、Token 或费用。
- P11 再做 OpenTelemetry、Prometheus、并发负载、真实 P95、错误率和故障演练。
- 若更换 OpenRouter 模型或模型供应商，应生成独立报告，不能覆盖不同 provider/model 的历史证据。
