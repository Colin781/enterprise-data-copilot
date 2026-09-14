# P5 安全 NL2SQL 验收记录

## 本阶段目标

把自然语言问题接到 P4 的结构化模型适配层，并让模型生成内容只能沿着已经验证过的安全纵向切片进入业务数据库。P5 负责生成、确定性检查、成本判断和有限修复；P7 才负责工作流持久化与人工审批恢复。

## 已实现能力

1. **问题入口拒绝**：写入、规则绕过、凭据、跨租户、敏感字段和任意代码请求在调用模型前直接拒绝。
2. **相关表选择**：第一轮模型只看到表名、表说明和关联表名，不看到全部字段；最多选择 6 张表。
3. **最小 schema 上下文**：第二轮仅发送已选表的字段、类型、主键和选中范围内的外键。
4. **结构化输出**：模型必须返回 `analysis_plan`、`tables_used` 和单条 `sql`，额外字段或类型错误由 P4 的 Pydantic 机制拒绝。
5. **列级 allowlist**：SQLGlot 根据固定元数据快照解析和限定字段；未知或未授权字段在数据库规划前被拒绝。`SELECT *` 会按允许字段展开，`COUNT(*)` 保持聚合语义。
6. **查询形状检查**：显式/隐式笛卡尔积、`JOIN ... ON TRUE` 和递归 CTE 被拒绝；原有 DDL、DML、COPY、多语句、跨 schema、危险函数与行锁防线继续生效。
7. **真实成本检查**：安全 SQL 在只读事务中执行 `EXPLAIN (FORMAT JSON)`，读取 `Total Cost` 和 `Plan Rows`。超过任一阈值时记录 `APPROVAL_REQUIRED`，查询执行器不会被调用。
8. **有限安全修复**：策略或数据库执行失败时，只把稳定错误码和上一次候选 SQL交给模型；不传原始数据库异常、连接信息或数据行。初稿后最多修复两次。
9. **审计扩展**：审计事件新增是否调用规划器、估算成本和估算行数，不保存 SQL 原文或业务结果。

## 关键代码

- `agent-service/app/nl2sql/`：问题检查、表选择提示、结构化计划、生成/修复编排和 execution accuracy 比较。
- `agent-service/app/query_safety/guard.py`：列级白名单、笛卡尔积与递归查询检查。
- `agent-service/app/query_safety/cost.py`：PostgreSQL 只读 JSON EXPLAIN 成本估算。
- `agent-service/app/query_safety/service.py`：成本门槛、审批分支、执行与审计闭环。
- `agent-service/tests/test_nl2sql.py`：离线功能、修复上限和攻击回归测试。
- `agent-service/tests/test_p5_integration.py`：真实 PostgreSQL 成本、修复和 15 题执行结果对比。
- `evaluation/northwind/p5-pipeline-baseline.json`：可追溯的阶段性离线流水线基线，明确区分真实数据库执行与真实模型质量。

## 安全边界

- 高成本查询在 P5 只会进入“需要审批”状态，不会自动放行；审批人的权限校验和恢复执行属于 P7。
- 表选择是缩小模型上下文与降低误用概率的机制，真正的授权仍由 SQL AST 表/列白名单和数据库只读账号执行。
- Fake LLM 离线评测证明流水线与 15 个候选 SQL 可以正确运行，不代表任意真实模型有 100% 的 NL2SQL 准确率。
- 真实模型上线前仍需人工确认供应商是否可靠支持当前 JSON Schema，并用相同 gold 集单独测量。

## 验证命令

```bash
make compose-up
make verify-p5
```

## 验收结果

2026-09-14 在本地完成以下实测：

- `make verify-p5`：27 passed，其中 3 项连接真实 PostgreSQL。
- 阶段性 execution accuracy：15/15（100%）。候选由 Fake LLM 按固定 gold 候选脚本提供，候选与标准答案均在真实 PostgreSQL 执行并比较字段和有序结果行；该数字只证明 P5 流水线基线，不代表真实模型准确率。
- 危险问题回归：8 种请求均在模型调用和数据库调用前拒绝。
- 模型 SQL 攻击回归：DDL、DML、COPY、多语句、未知/敏感字段、跨 schema、笛卡尔积、递归 CTE、注释/大小写与嵌套写操作均到达规划器 0 次、到达执行器 0 次。
- 修复上限：初稿加最多两次修复；连续三次字段违规后明确失败，执行器调用 0 次。
- 真实数据库错误修复：首轮失败、第二轮成功；修复提示只含 `QUERY_EXECUTION_FAILED`，不含 PostgreSQL 原始异常、主机、用户名或密码。
- 真实成本门槛：`EXPLAIN (FORMAT JSON)` 产生估算值；超阈值事件为 `APPROVAL_REQUIRED`，执行器调用 0 次。
- Python 全量回归（启用 P2、安全纵切和 P5 的全部真实数据库测试）：91 passed。
- Java 全量格式检查与构建：BUILD SUCCESS，13 passed（其中 6 项 Testcontainers PostgreSQL）。
- Web：ESLint、TypeScript 类型检查和 Next.js 生产构建全部通过。
- Docker Compose 配置校验通过；Python 锁文件离线同步成功（58 个包解析、56 个包检查）。

远程 GitHub Actions 仍需在仓库首次提交并推送后确认。当前仓库还没有第一次 Git 提交，因此以上结论只陈述已经实际执行的本地证据。
