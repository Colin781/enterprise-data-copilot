# P8 异步执行、Redis 进度与 SSE 验收记录

## 本阶段目标

把 P7 已验证的同步内部工作流升级为浏览器可用的异步任务链，同时继续保持 Java/PostgreSQL 是任务权威源。P8 的退出证据严格对应收敛版路线：创建任务不等待 Python、SSE 断线后能按事件 ID 续传、事件顺序稳定、Redis 丢失不影响最终任务结果。

## 已实现能力

1. **提交即返回**：分析任务先在 Java 事务中落库，事务提交后才投递到有界后台线程池。`POST /api/analysis/jobs` 返回 `202 + jobId`，不会等待 Python Agent 完成。
2. **有界执行与恢复**：线程池的核心线程、最大线程和队列容量均可配置；队列拒绝会把任务落为 `FAILED/ASYNC_QUEUE_FULL`。应用启动时会重新投递 PostgreSQL 中的 `CREATED/PLANNING` 任务，Python 仍用 `jobId` 幂等启动同一工作流。
3. **跨服务重试**：调用 Python `/internal/v1/runs` 最多尝试三次，使用同一 `Idempotency-Key`；耗尽后把稳定错误码写入 PostgreSQL，不把连接异常暴露给浏览器。
4. **Redis 短期事件流**：每个任务使用独立 Redis Stream。Lua 脚本在一次原子操作中递增 `sequence` 并追加事件，事件保留时间和最大长度均有上限。
5. **完整事件信封**：事件包含 `event_version/event_id/sequence/job_id/tenant_id/trace_id/type/status/occurred_at/payload`。步骤事件只带步骤名、尝试次数、状态和稳定错误码，不携带问题、SQL 明文或结果行。
6. **SSE 订阅与续传**：`GET /api/analysis/jobs/{jobId}/events` 只允许任务所有者或同租户管理员访问。服务使用 SSE `id` 写入 `event_id`，并按 `Last-Event-ID` 重放后续事件，再继续推送实时事件。
7. **无重放缝隙**：单进程内同一任务的“注册订阅者、读取历史、发布新事件”共享任务级临界区，避免在历史读取与实时订阅之间漏掉事件。
8. **PostgreSQL 权威终态**：Python 的最终状态、workflow thread、SQL、答案和稳定错误码写入 `analysis_jobs`。Redis 不可用时事件发布降级为实时临时事件；历史不可用时 SSE 返回 PostgreSQL `JOB_SNAPSHOT`，任务查询和最终结果不受影响。
9. **审批事件接入**：Agent 步骤、审批请求和审批决定都在各自数据库事务成功提交后发布，避免 SSE 先看到尚未落库的状态。

## 事件与状态边界

- Redis 仅保存短期进度和分发租约，不保存唯一业务事实。
- PostgreSQL 保存任务状态、最终结果、审批和步骤；页面刷新后始终可通过任务 API 恢复。
- Redis Stream 的 `sequence` 只在单个 `jobId` 内单调递增；客户端不应跨任务比较序号。
- `Last-Event-ID` 已超出保留窗口或 Redis 已丢失时，服务发送 PostgreSQL 快照，客户端随后以任务查询结果为准。
- 多实例重复投递由 Redis 短租约减少，最终仍由 Java 任务状态和 Python `jobId/thread_id` 幂等语义兜底。

## 验收证据

`make verify-p8` 使用真实 PostgreSQL 17 和 Redis 8.2 Testcontainers，验证：

- Python 边界被阻塞时，创建接口仍在 1 秒内返回 `202`；
- 第一次临时调用失败后使用同一任务重试并成功完成；
- `CREATED → PLANNING → COMPLETED` 事件序号严格递增且无重复；
- 以已接收 `event_id` 断开后，重连只返回其后的事件；
- 清空 Redis 后，PostgreSQL 中仍保留 `COMPLETED`、SQL、答案和完成时间；
- Redis 历史丢失时，SSE 返回来源为 PostgreSQL 的 `JOB_SNAPSHOT`。
- 平台启动恢复会重新投递 PostgreSQL 中未完成的任务，并沿用原 `jobId/thread_id`。

2026-09-15 本地实测结果：

- P8 定向验收：2 passed；
- Java 全量回归：17 passed；
- OpenAPI 与事件契约：11 passed；
- Python 全量联合回归：122 passed（P2～P7 数据库集成开关全部启用、无跳过项）；
- Java Spotless、Python Ruff、Compose 配置、Web ESLint/TypeScript 和 Next.js 生产构建均通过。

## 明确留给后续阶段

- P9 已完成登录、任务提交、审批、步骤时间线、SQL/表格/图表的完整页面；
- P10：50+ NL2SQL、20+ RAG 的真实模型质量评测；
- P11：OpenTelemetry、指标、并发/P95 报告和故障演练；
- Kafka/RabbitMQ、死信队列和跨进程 SSE fan-out 仍是有规模证据后再引入的工程增强，不是 P8 完成条件。
