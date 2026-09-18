# P7 LangGraph Agent 与人工审批验收记录

## 本阶段目标

把 P5 的安全 NL2SQL 与 P6 的指标检索接入可持久化工作流，并保持 Java 是任务、审批和审计的权威源。P7 的退出证据严格对应收敛版路线：进程重启后可恢复、同一审批只能处理一次、Agent 循环有硬上限。

## 已实现能力

1. **完整条件图**：`classify → retrieve_metrics → select_schema → generate_sql → guard_sql → request_approval/execute_sql → verify → compose`。知识问答会在检索后直接组合带引用的答案；危险自然语言请求会在进入模型和数据库前终止。
2. **P5/P6 生产适配器**：工作流节点复用指标混合检索、schema introspection、结构化 LLM、SQLGlot guard、PostgreSQL `EXPLAIN` 和只读执行器，不另建一套绕过安全链的执行路径。
3. **PostgreSQL checkpointer**：使用官方 `langgraph-checkpoint-postgres`，`jobId` 是稳定 `thread_id`。首次启动执行 checkpointer migrations；恢复时只需同一个 ID，不依赖原 Python 对象或连接。checkpoint 反序列化启用 strict msgpack。
4. **动态中断与恢复**：成本超阈值、受控敏感列或表选择置信度低于阈值时调用 `interrupt`。Java 管理员作出决定后，使用 `Command(resume=...)` 恢复同一 checkpoint；拒绝不会执行 SQL。
5. **确定性拒绝边界**：写操作、跨 schema/租户、安全绕过、密钥请求和任意代码请求始终拒绝，不能通过管理员审批放行。
6. **有限修复**：SQL guard 或结果验证失败最多修复两次，即初稿加两次修复共三次生成；之后以稳定错误状态结束。
7. **摘要化步骤记录**：Flyway V4 创建 `agent_steps`。每个节点通过内部服务令牌回写 Java，只保存计数、原因码、引用数量和 SQL SHA-256 指纹，不保存问题、SQL 明文或业务行值。重放键让相同节点状态写入幂等。
8. **Java 权威审批**：审批表行使用悲观锁，决定前再次校验租户与 `PENDING` 状态。Java 在事务中调用 Python `/resume`，成功后才提交审批与任务状态；重复决定返回 `409 APPROVAL_ALREADY_DECIDED`。
9. **刷新可见性**：既有任务查询返回 PostgreSQL 中的权威状态，新增 `/api/analysis/jobs/{jobId}/steps` 返回按时间排序的租户内轨迹。P8 已在此基础上补充 SSE 实时推送与断线续传。

## 数据库与契约

Flyway V4：

- 为 `analysis_jobs` 预留 workflow thread、SQL、答案和错误字段；
- 新建租户归属明确的 `agent_steps`；
- 使用 `(analysis_job_id, step_name, attempt, status)` 唯一约束吸收节点重放；
- 建立任务时间序和租户任务索引。

内部 Agent API 新增 `/internal/v1/runs/{runId}/resume`，要求服务令牌、受信租户头和 `ADMIN` 角色头。浏览器 API 新增审批批准/拒绝和步骤读取契约；浏览器仍不能直接访问 Python。

## 验收证据

`make verify-p7` 覆盖：

- 安全路径经过 8 个节点并成功结束；
- 高成本、敏感字段和低置信度共用持久化审批门；
- 拒绝与永久策略阻断到达执行器次数为 0；
- 同一个 checkpoint 第二次恢复返回冲突，执行器只调用一次；
- 连续验证失败时恰好生成三次后停止；
- Agent Service API 的服务令牌和管理员恢复约束；
- 关闭 PostgreSQL checkpointer 连接、重建工作流服务后，仍能读取中断并完成恢复。

Java Testcontainers 额外验证 Flyway V1～V4 从空库迁移、管理员审批事务、重复审批拒绝，以及 Python `/resume` 只被调用一次。

2026-09-15 本地实测结果：

- `make verify-p7`：15 passed，其中 1 项关闭 PostgreSQL checkpointer 连接并重建服务后恢复；
- Python P2～P7 全量联合回归：121 passed，所有数据库集成开关均启用，无跳过项；
- Java：15 passed；Flyway V1～V4 从空库执行成功，审批重复提交仅调用一次 `/resume`；
- Python Ruff、Java Spotless、OpenAPI、Compose 配置、Web ESLint/TypeScript 与 Next.js 生产构建均通过。

## 明确留给后续阶段

- P8 已完成：后台任务池、Redis 短期进度、SSE、断线重连和跨服务投递重试；
- P9：审批页、执行轨迹、结果表格和图表 UI；
- P10：真实供应商模型下的端到端质量评测，以及真实 embedding 对比；
- P11：checkpoint/step 保留策略、跨服务 trace、指标与性能报告。

P7 使用同步内部调用语义来证明恢复与审批正确性，不将它描述为高吞吐异步生产架构；后者是 P8 的验收范围。
