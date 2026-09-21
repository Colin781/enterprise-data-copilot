# P11 可观测性、性能与部署验收

## 退出结论

P11 的仓库内交付已完成：W3C Trace Context 在浏览器入口、Java、Python 和内部回调间传播；Python 每个 LangGraph 节点建立 OpenTelemetry span；Java/Python 暴露 Prometheus 指标；三服务都有多阶段容器镜像；全栈 Compose 包含数据库、Redis、应用与 Prometheus；k6 场景覆盖并发任务创建和 SSE 终态。

公网 Demo 没有在本阶段伪造为已部署。`docker-compose.full.yml` 是可发布构件，真正公网发布仍需要由部署者提供域名、TLS、Secret Manager 和云账号。

## Trace 证据

- Java `TraceIdFilter` 接受严格的 W3C `traceparent`，拒绝全零 trace/span id，为每个入站请求创建新的 server span id，并返回 `traceparent` 与兼容的 `X-Trace-Id`。
- Java 调用 Agent 与知识接口时生成新的 child span id；审批恢复继续使用原任务 trace id。
- Python 严格解析 version `00` 的 `traceparent`，每个 `agent.node.*` 节点创建 OpenTelemetry span。
- span 属性只包含节点名与稳定错误码，不包含问题、SQL、邮箱、DSN 或结果行。

## Prometheus 指标

| 指标 | 来源 | 用途 |
|---|---|---|
| `http_server_requests_seconds_*` | Spring/Micrometer | Java 请求数、错误率和 P95 |
| `copilot_agent_client_duration_seconds_*` | Java | Java → Python 调用延迟 |
| `copilot_agent_client_errors_total` | Java | Agent 调用错误率 |
| `copilot_agent_http_requests_total` | Python | Agent 请求数与状态 |
| `copilot_agent_http_request_duration_seconds_*` | Python | Agent HTTP 延迟 |
| `copilot_agent_node_duration_seconds_*` | Python | 检索、模型、数据库、审批等节点延迟 |
| `copilot_agent_node_errors_total` | Python | 节点稳定错误码 |
| `copilot_agent_model_tokens_total` | Python | provider 返回的输入/输出 Token |
| `copilot_agent_sql_rejections_total` | Python | 确定性策略拒绝数 |

抓取地址：Java `/actuator/prometheus`，Python `/metrics`，本地 Prometheus `http://localhost:9090`。

## 完整部署

```bash
make env
# 先把 .env 中的示例密码、JWT secret、服务 token 和模型 key 替换掉
make stack-config
make stack-up
```

`stack-up` 构建 Java 21、Python 3.12 和 Node 24 多阶段镜像，启动 Platform PostgreSQL、Northwind PostgreSQL、Redis、Platform API、Agent Service、Web 和 Prometheus，并等待健康检查。

停止但保留数据库卷：

```bash
make stack-down
```

## 无模型费用的负载场景

`make p11-load` 使用 k6 并发提交“删除所有订单”。请求会走登录、任务、Redis/SSE、LangGraph、问题策略拒绝和最终状态落库，但在调用模型前结束。默认阈值：错误率 `<1%`、任务创建 P95 `<2s`、SSE 终态 P95 `<5s`。

本地实测结果保存于 `evaluation/p11-local-performance.json`。它只表示报告中记录的机器、并发和时长，不应描述成公网容量。

当前实测：5 VU、10 秒、717 次完整迭代、1436 个 HTTP 请求、错误率 0%；任务创建 P95 7.54 ms，收到终态 SSE P95 85.71 ms。该场景在模型调用前被确定性拒绝，因此 Token/费用为 0，但也不包含真实模型延迟。

完整 Compose 也已实际启动验收：7 个服务全部运行，6 个配置了 Compose 健康检查的服务均为 `healthy`，Prometheus readiness 通过；Platform 与 Agent 两个 Prometheus target 均为 `up`，容器化 Web 代理登录返回 200。通过 Platform 提交的无模型费用危险问题最终经 Agent 返回 `REJECTED`，入站 W3C trace id 在响应头、任务事件和终态 SSE 中保持一致。首次启动验收还发现空 `OBSERVABILITY_OTLP_HTTP_ENDPOINT` 会被当成非法 URL；配置层现已把空白值规范化为“未启用导出”，并加入回归测试。

## 故障与安全验证

- WireMock 覆盖 Agent 500、超时、非法 JSON、缺字段与成功响应。
- Redis 不可用时 PostgreSQL 最终状态仍为权威源。
- 数据源登记受 `PLATFORM_DATA_SOURCE_ALLOWED_HOSTS` 限制，演示部署不能登记任意公网数据库。
- 数据库响应不返回 host、DSN 或 `secret_ref`；运行时密钥只通过环境/Secret Manager 注入，未写入镜像。
- Agent 步骤和 SQL 审计只保存 allowlist 摘要及指纹，不保存问题全文、SQL 参数或结果值。

## 验收命令

```bash
make verify-p11
```

该命令校验 Compose、Java trace/WireMock、Python metrics/trace 解析和工作流节点指标。完整镜像构建与运行使用 `make stack-up` 单独验证。
