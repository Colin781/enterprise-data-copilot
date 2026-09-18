# 两次本地运行故障的定位与解决记录

本文记录 P9 完成后实际启动与端到端运行时遇到的两个主要用户可见问题：

1. Agent 启动和指标文档上传链路失败。
2. 自然语言分析任务卡在“规划中”或最终失败。

每个问题都不是单一错误，而是跨配置、HTTP、鉴权、异步运行时、模型输出和结果验证的多层问题。本记录保留完整排查过程，便于以后回归。

---

## 问题一：Agent 启动失败，指标文档上传返回 500

### 1. 用户可见现象

最初执行：

```bash
make dev-agent
```

Agent 在启动阶段退出，关键异常为：

```text
ValidationError: AgentWorkflowSettings
max_repairs
Input should be 2
input_value='2'
```

修正启动后，在 Web 的“指标知识库”上传 Markdown 时仍返回：

```text
The platform could not complete the request.
```

Web 日志显示：

```text
POST /api/platform/metric-documents 500
```

Agent 日志先后出现：

```text
POST /internal/v1/knowledge/documents 401 Unauthorized
POST /internal/v1/knowledge/documents 422 Unprocessable Entity
POST /internal/v1/knowledge/documents 201 Created
```

Uvicorn 还出现过：

```text
Unsupported upgrade request.
Invalid HTTP request received.
```

这说明浏览器中的 500 不是一个错误的简单重复，而是调用链上多个问题先后被暴露。

### 2. 调用链

指标文档上传经过：

```text
浏览器
  -> Next.js /api/platform/metric-documents
  -> Java Platform API /api/metric-documents
  -> Python Agent /internal/v1/knowledge/documents
  -> Platform PostgreSQL + pgvector
```

浏览器只携带用户 JWT。Java 调用 Python 时改用共享服务 token，并附带租户和用户头。

### 3. 根因一：Pydantic `Literal` 与环境变量字符串不兼容

`.env` 中的值天然以字符串进入进程：

```dotenv
AGENT_WORKFLOW_MAX_REPAIRS=2
RAG_EMBEDDING_DIMENSIONS=64
```

原实现使用：

```python
max_repairs: Literal[2]
embedding_dimensions: Literal[64]
```

Pydantic Settings 收到的是字符串 `'2'` 和 `'64'`。严格 `Literal` 不接受环境变量转换后的字符串，因此应用在 lifespan 创建工作流前就退出。这不是 LangGraph 或业务构建错误。

### 4. 对根因一的最终修复

固定值改为带上下界的整数字段：

```python
max_repairs: int = Field(default=2, ge=2, le=2)
embedding_dimensions: int = Field(default=64, ge=64, le=64)
```

这样仍然保证值只能是 2 和 64，同时允许 Settings 正常把环境字符串解析为整数。

对应位置：

- `agent-service/app/settings.py`

### 5. 根因二：两个服务间 token 的含义和位置不清楚

需要配置：

```dotenv
AGENT_SERVICE_TOKEN=<同一个随机字符串>
AGENT_WORKFLOW_SERVICE_TOKEN=<同一个随机字符串>
```

它们不是 OpenRouter 或其他平台发放的 token，而是项目运行者自行生成的内部共享凭据。

生成方式：

```bash
openssl rand -hex 32
```

两个变量分别由不同服务读取：

- Java Platform 使用 `AGENT_SERVICE_TOKEN` 调用 Python Agent。
- Python Agent 使用 `AGENT_WORKFLOW_SERVICE_TOKEN` 验证请求，并回调 Java Platform。

如果值不同，Agent 会返回 401。修改 `.env` 后只刷新浏览器没有作用，Platform 和 Agent 都必须重启，因为它们在启动时读取环境变量。

### 6. 根因三：Spring JWT 过滤器错误处理内部共享 token

Java Platform 同时存在两类 Bearer token：

- `/api/**` 使用标准用户 JWT。
- `/internal/**` 使用共享服务 token，由内部控制器做常量时间比较。

原 Spring Resource Server 会先把 `/internal/**` 的共享 token 当成 JWT 解码。共享 token 不是 JWT，因此请求在进入内部控制器前就被 401 拒绝。

仅把 `/internal/**` 配成 `permitAll()` 不够，因为 Bearer token 过滤器仍会看到 `Authorization` 头并尝试解析。

### 7. 对根因三的最终修复

在 `SecurityConfiguration` 中加入自定义 `DefaultBearerTokenResolver`：

```text
/internal/** -> 不交给 JWT 解码器
其他路径      -> 按正常 Bearer JWT 处理
```

内部接口并不是因此变成匿名接口。请求进入控制器后，仍然必须通过共享服务 token 校验。

对应位置：

- `platform-api/src/main/java/com/example/copilot/security/SecurityConfiguration.java`

同时增加集成测试，验证：

- 合法共享 token 可以调用内部接口。
- 错误共享 token 仍被拒绝。
- `/api/**` 的用户 JWT 行为不受影响。

### 8. 根因四：Java 到 Uvicorn 的 HTTP 协议与响应反序列化不稳定

Java `RestClient` 的底层客户端可能尝试协议升级，Uvicorn 因此记录：

```text
Unsupported upgrade request.
Invalid HTTP request received.
```

此外，直接让 `RestClient` 把 Python JSON 响应绑定成 Java record，在当前 Spring Boot/Jackson 组合中不够稳定，可能出现 Agent 已返回 201，但 Platform 仍返回 500 的情况。

### 9. 对根因四的最终修复

两个 Java Agent 客户端都显式使用 HTTP/1.1：

- `HttpMetricKnowledgeClient`
- `HttpAgentRunClient`

并统一采用：

```text
先读取 String 响应体
再使用 Spring Boot 管理的 ObjectMapper 解析
```

这样避免协议升级噪声，也保证 Platform 与项目实际 Jackson 配置一致。

对应位置：

- `platform-api/src/main/java/com/example/copilot/integration/agent/HttpMetricKnowledgeClient.java`
- `platform-api/src/main/java/com/example/copilot/integration/agent/HttpAgentRunClient.java`

### 10. 问题一的最终结果

修复后：

- `make dev-agent` 能完成应用启动。
- `/internal/v1/knowledge/documents` 使用正确服务 token 后返回 `201 Created`。
- Web 的指标文档上传不再返回 500。
- Markdown 能解析、切块、写入索引并显示为 `ACTIVE`。
- Java 内部接口仍保持鉴权边界，没有因为跳过 JWT 解析而放开匿名访问。

### 11. 问题一的回归检查

```bash
cd platform-api
./mvnw -Dtest=PlatformSecurityIntegrationTest test
```

```bash
cd agent-service
./.venv/bin/pytest -q tests/test_knowledge_api.py
```

浏览器人工验收：

1. 管理员登录。
2. 上传 `knowledge/northwind/retail-metrics-v1.md`。
3. Web 不出现 500。
4. Agent 日志出现 `201 Created`。
5. 页面显示新文档版本。

---

## 问题二：分析任务卡在规划，日志显示 Agent 500

### 1. 用户可见现象

提交：

```text
1997 年每季度销售额是多少？
```

页面长时间停留在“规划中”。Web 持续轮询任务与步骤：

```text
GET /api/platform/analysis/jobs/{jobId}
GET /api/platform/analysis/jobs/{jobId}/steps
```

Java 后台任务记录：

```text
I/O error on POST request for http://localhost:8000/internal/v1/runs
```

Agent 的真实异常为：

```text
RuntimeError: no running event loop
```

异常处理过程中又出现：

```text
RuntimeError: Event loop is closed
```

修复该错误后，流程能进入 `generate_sql`，但又出现：

```text
NL2SQL_SCHEMA_SELECTION_FAILED
```

继续修复后，有数据的 2025 问题又暴露：

```text
RESULT_COLUMNS_MISMATCH
```

因此该问题也包含多个连续根因。

### 2. 根因一：跨 `asyncio.run()` 复用 `httpx.AsyncClient`

LangGraph 当前使用同步节点。每个需要模型的节点通过：

```python
asyncio.run(coroutine)
```

执行异步 LLM 调用。

执行顺序是：

```text
select_schema  -> asyncio 事件循环 A -> 完成后循环 A 被关闭
generate_sql   -> asyncio 事件循环 B
```

原 `OpenAICompatibleProvider` 在构造时创建一个长期复用的 `httpx.AsyncClient`。第一次请求后，它的连接池仍绑定事件循环 A；第二次模型调用在事件循环 B 中复用该客户端，于是触发：

```text
RuntimeError: Event loop is closed
```

这解释了为什么第一轮选表可以成功，而第二轮生成 SQL 时失败。

### 3. 对事件循环问题的最终修复

生产环境不再跨节点保存自有 `AsyncClient`。每次 `complete()` 调用都在当前事件循环中创建并关闭短生命周期客户端：

```python
async with httpx.AsyncClient(base_url=...) as client:
    response = await client.post(...)
```

测试注入的客户端仍由调用方管理，不改变单元测试与集成边界。

对应位置：

- `agent-service/app/llm/openai_compatible.py`

新增回归测试连续执行两个独立 `asyncio.run()`，确认会创建两个分别绑定各自事件循环的客户端。

### 4. 根因二：图异常没有转换为任务终态

LangGraph 节点抛异常时，错误已经保存在 PostgreSQL checkpoint 的 task error 中，但 `AgentWorkflowService.start()` 原先继续把异常抛回 Java。

Java 把它视为临时 I/O 失败并有限重试。平台任务没有收到明确的 Agent 终态，于是用户看到任务长时间停在 `PLANNING`。

### 5. 对任务终态问题的最终修复

`AgentWorkflowService` 现在会：

1. 捕获图执行异常。
2. 重新读取当前 LangGraph checkpoint。
3. 检查持久化 task error。
4. 把已知异常映射为稳定错误码。
5. 返回 `FAILED`，而不是让 Java 将其误判为网络重试。

映射包括：

| 异常 | 稳定错误码 |
|---|---|
| `LLMAuthenticationError` | `LLM_AUTHENTICATION_ERROR` |
| `LLMConfigurationError` | `LLM_CONFIGURATION_ERROR` |
| `LLMInvalidResponseError` | `LLM_INVALID_RESPONSE` |
| `LLMRateLimitError` | `LLM_RATE_LIMITED` |
| `LLMRequestRejectedError` | `LLM_REQUEST_REJECTED` |
| `LLMTimeoutError` | `LLM_TIMEOUT` |
| `LLMUnavailableError` | `LLM_UNAVAILABLE` |
| 其他工作流异常 | `AGENT_WORKFLOW_FAILED` |

对应位置：

- `agent-service/app/agent/service.py`

这样即使以后模型或节点再次失败，页面也会进入明确的失败状态，不会无限显示规划中。

### 6. 根因三：OpenRouter Key 有效，但原模型请求被 403 拒绝

对 OpenRouter 的验证结果是：

- `GET /api/v1/auth/key` 返回 200，说明 API Key 有效。
- 请求原模型 `openai/gpt-4.1-mini` 返回 403。
- 返回信息表明请求被供应商条款策略拒绝，而不是项目 JSON、SQL 或网络错误。

原适配器把 401 和 403 都归为认证错误，导致诊断方向不准确。

### 7. 对 OpenRouter 错误分类和模型的最终处理

HTTP 错误现在区分：

```text
401 -> LLM_AUTHENTICATION_ERROR
403 -> LLM_REQUEST_REJECTED
```

随后在 OpenRouter 内部对支持 structured output 的模型做真实验证，最终固定：

```dotenv
LLM_PROVIDER=openrouter
LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
```

这只是 OpenRouter 内部切换模型，没有切换模型供应商。若未来需要从 OpenRouter 切到其他模型源，必须先由项目负责人确认。

### 8. 根因四：SQL prompt 没有把允许的 schema 明确发给模型

第一次修复事件循环后，`select_schema` 已成功选出：

```text
orders
order_details
```

但生成 SQL 的 prompt 只发送表和字段，没有发送允许的 schema 名。系统提示又要求模型使用 schema-qualified table，于是模型自行猜测：

```text
public.orders
public.order_details
```

`tables_used` 也返回带 `public.` 前缀的值。安全校验正确拒绝了它，并给出：

```text
NL2SQL_SCHEMA_SELECTION_FAILED
```

这不是安全校验器太严格，而是 prompt 缺失了关键上下文。

### 9. 对 schema 问题的最终修复

生成请求现在显式包含：

```json
{
  "allowed_schema": "northwind",
  "schema": []
}
```

系统提示同时明确：

- SQL 中每个物理表必须使用 `allowed_schema`。
- `tables_used` 只能复制 schema 数组中的裸表名。
- 不允许模型自行添加其他 schema。

服务端校验器允许两种等价报告：

```text
orders
northwind.orders
```

但仍拒绝：

```text
public.orders
other_schema.orders
```

SQL AST guard 仍是最终安全边界；prompt 修正没有放宽跨 schema 限制。

对应位置：

- `agent-service/app/nl2sql/prompts.py`
- `agent-service/app/nl2sql/table_references.py`
- `agent-service/app/nl2sql/service.py`
- `agent-service/app/agent/actions.py`

### 10. 根因五：模型把列说明写进 `expected_columns`

SQL 已成功执行并返回：

```text
quarter
sales
```

但模型的分析计划返回：

```text
quarter (text, e.g. '2025-Q1')
sales (numeric)
```

`verify` 节点按精确列名比较，因此判定：

```text
RESULT_COLUMNS_MISMATCH
```

工作流随后重复生成和执行 SQL，但模型不知道真正错误是“列名中混入说明”，所以重试无法解决。

### 11. 对列验证问题的最终修复

`AnalysisPlan.expected_columns` 的 Pydantic schema 现在只接受小写 SQL 标识符：

```text
^[a-z_][a-z0-9_]*$
```

提示中也明确要求：

```text
expected_columns 必须是实际 SQL 输出别名，不得附带类型和说明。
```

季度时间序列统一要求返回：

```sql
date_trunc('quarter', order_date)::date AS quarter_start
```

避免模型用易出错的 `to_char` 格式字符串自行拼季度标签。

对应位置：

- `agent-service/app/nl2sql/models.py`
- `agent-service/app/nl2sql/prompts.py`

### 12. 根因六：PostgreSQL numeric 被序列化成字符串，图表误判

查询最终返回：

```json
{
  "quarter_start": "2025-01-01",
  "total_sales": "4151.76000"
}
```

为避免 Decimal 精度损失，`numeric` 被 JSON 序列化为字符串。原图表推断只认 Python `Number`，因此把结果退化成 table，而不是 line。

### 13. 对图表问题的最终修复

图表推断现在额外接受可被 `Decimal` 安全解析的有限数值字符串，并继续拒绝日期、空字符串、NaN 和 Infinity。

前端原本就使用安全的 `Number(value)` 转换数值，因此无需执行任意代码或原始 HTML。

对应位置：

- `agent-service/app/agent/charting.py`
- `agent-service/tests/test_charting.py`

### 14. 1997 年问题为什么返回 0 行

仓库使用的不是完整经典 Northwind 历史库，而是固定夹具：

```text
northwind-compact-v1
```

其中订单日期只覆盖 2024～2025 年。因此：

```text
1997 年每季度销售额是多少？
```

修复后会正常完成，但返回 0 行。它不再卡在规划，也没有执行错误；结果为空是因为数据集中没有 1997 年订单。

为了验证有数据时的完整链路，最终采用：

```text
2025 年每季度销售额是多少？
```

### 15. 最终端到端验收结果

最终任务：

```text
fa6c0de0-398b-43b3-a980-baf79f0f8fd7
```

结果：

```text
status     = COMPLETED
error_code = null
```

生成 SQL：

```sql
SELECT
  date_trunc('quarter', o.order_date)::date AS quarter_start,
  SUM(od.unit_price * od.quantity * (1 - od.discount)) AS total_sales
FROM northwind.orders o
JOIN northwind.order_details od ON o.order_id = od.order_id
WHERE o.order_date >= DATE '2025-01-01'
  AND o.order_date < DATE '2026-01-01'
GROUP BY date_trunc('quarter', o.order_date)
ORDER BY quarter_start;
```

实际结果：

| quarter_start | total_sales |
|---|---:|
| 2025-01-01 | 4151.76000 |
| 2025-04-01 | 4103.62600 |

图表规格：

```json
{
  "type": "line",
  "title": "分析结果",
  "x": "quarter_start",
  "series": ["total_sales"]
}
```

执行轨迹全部成功：

```text
classify          SUCCEEDED
retrieve_metrics  SUCCEEDED
select_schema     SUCCEEDED
generate_sql      SUCCEEDED
guard_sql         SUCCEEDED
execute_sql       SUCCEEDED
verify            SUCCEEDED
compose           SUCCEEDED
```

### 16. 自动化回归结果

最终 Python 全量测试：

```text
114 passed, 16 skipped
```

同时通过：

- Ruff format check。
- Ruff static check。
- Java `PlatformSecurityIntegrationTest`。
- Web Node tests、ESLint 和 TypeScript typecheck。
- 真实 Platform -> Agent -> OpenRouter -> Northwind -> Platform 端到端任务。

### 17. 以后再次出现类似问题时的排查顺序

不要只盯着 Web 的 500 或“规划中”。按以下顺序定位：

1. 三个服务的 `/health` 是否都是 `UP`。
2. Platform 日志是否成功调用 `/internal/v1/runs` 或 `/internal/v1/knowledge/documents`。
3. Agent 是否返回 401、422、500 或 2xx。
4. 两个服务 token 是否一致，修改后是否重启双方。
5. OpenRouter Key 检查成功不代表指定模型一定可用；区分 401、403、429。
6. 查询 LangGraph checkpoint 的 task error，确认实际失败节点。
7. 对比 `candidate_tables`、`tables_used`、SQL 物理表和 `allowed_schema`。
8. 对比分析计划 `expected_columns` 与数据库实际 `columns`。
9. 有结果但无图表时，检查数值是否以 Decimal 字符串返回。
10. 最后核对固定数据的年份和覆盖范围，避免把正确的空结果误判为系统故障。

### 18. 结论

两个问题最终都不是通过放宽安全边界解决的：

- 内部接口仍验证共享 token。
- 用户接口仍验证 JWT。
- SQL 仍只允许 Northwind、只读、单语句和元数据白名单内资源。
- 模型错误仍转换成可追踪的稳定错误码。
- 跨 schema 输出仍被拒绝。

最终修复的核心是让配置解析、HTTP 协议、鉴权层次、异步客户端生命周期、模型上下文和结果契约彼此一致。
