# 本地开发

## 前置工具

- Java 21（项目包含 Maven Wrapper，无需全局 Maven）
- Python 3.12 与 uv
- Node.js 22+ 与 pnpm 11
- Docker Desktop / Docker Engine 与 Compose

## 第一次启动

```bash
make env
make compose-up
make setup
make dev
```

`make env` 只在 `.env` 不存在时复制模板。`.env` 已被 Git 忽略；其中的本地密码仍应按个人环境修改。

如果 `.env` 是 P3 之前创建的，请从 `.env.example` 补入 `PLATFORM_JWT_SECRET`、`PLATFORM_JWT_ISSUER` 和 `PLATFORM_ACCESS_TOKEN_TTL`。JWT secret 至少需要 32 字节，不能使用模板值部署到真实环境。

P4 增加了 `LLM_*` 配置。自动化测试使用 Fake LLM，不需要 API Key；只有人工调用真实供应商时，才需要把 `LLM_API_KEY` 写入被 Git 忽略的 `.env` 或由部署环境注入。

## 单独启动服务

```bash
make dev-platform  # http://localhost:8080/health
make dev-agent     # http://localhost:8000/health
make dev-web       # http://localhost:3000 and /health
```

## 验证

```bash
make compose-config
make test
make contract-test
make lint
make build
make verify-readonly
```

`make compose-up` 会在业务数据库达到 healthy 后幂等创建或更新只读账号，因此旧数据卷也能补齐 P1 权限基线。`make verify-readonly` 会验证查询成功、默认事务只读，并确认普通建表被 PostgreSQL 拒绝。

## P2 数据与元数据

`make compose-up` 还会幂等加载仓库内的 `northwind-compact-v1` 固定数据。它不会删除数据卷；重复运行会把固定主键对应的演示行恢复到版本定义的内容。

```bash
make load-northwind
make verify-p2
```

`make verify-p2` 会连接真实 PostgreSQL，验证固定数据行数、只读写入拒绝、跨 schema 拒绝、2 秒查询超时、元数据快照，以及 15 条首批 gold SQL。元数据程序的输出只包含表、列、类型、主外键和注释，不包含业务样例行。

如需人工查看当前元数据摘要：

```bash
cd agent-service
uv run python -m app.metadata.cli
```

提交前可检查数据库结构是否意外偏离已保存快照：

```bash
cd agent-service
uv run python -m app.metadata.cli --check ../metadata/northwind-schema-v1.json
```

## P3 Java 平台

Java 测试从 P3 起使用 Testcontainers 启动临时 PostgreSQL 17，因此执行 `make test` 时 Docker 必须可用。测试结束后临时容器会自动清理。

平台现在提供登录、租户内数据源登记、任务创建和任务查询接口。OpenAPI 定义位于 `contracts/openapi-platform.yaml`。初始租户和管理员不通过匿名互联网接口创建，应由部署流程在平台库中安全配置；自动化测试会为每个用例创建独立夹具。

数据库容器就绪不等于完整分析功能就绪。P3 会运行平台 Flyway 迁移，但调用 Python Agent、查询业务数据库和生成答案仍属于后续阶段；下游依赖的独立 readiness 语义也尚未实现。

## P4 模型适配与结构化输出

业务代码通过 `StructuredLLMClient` 请求 Pydantic 模型，不直接依赖供应商 SDK。默认适配 OpenRouter，也可以将 `LLM_PROVIDER`、`LLM_BASE_URL` 和 `LLM_API_KEY` 指向其他 OpenAI-compatible 服务；日常切换模型只需修改 `LLM_MODEL`。

```bash
make verify-p4
```

该命令只使用脚本化 Fake LLM 和内存 HTTP transport，不访问外网、不消耗模型额度。它会验证严格 JSON Schema 请求、Pydantic 响应校验、非法 JSON 只重试一次、超时指数退避、HTTP 错误分类，以及日志和异常不泄露提示词、模型响应、API Key 或连接信息。

真实模型连通性不是 P4 自动验收条件。P5 开始生成 NL2SQL 前，还需要根据所选模型做一次人工 structured-output 能力确认。

## P5 安全 NL2SQL

P5 将 P4 的结构化模型客户端接到既有安全执行链路之前。第一轮模型调用只能从不含完整字段信息的表目录中选择最多 6 张相关表；第二轮只会看到这些表的字段、主键和相关外键，并返回经过 Pydantic 校验的分析计划与单条 SQL。

```bash
make compose-up
make verify-p5
```

该命令使用 Fake LLM 的固定候选结果，不访问外网、不消耗模型额度，但候选 SQL 会连接真实 Northwind PostgreSQL。系统会做字段级白名单检查，拒绝写操作、未知字段、跨 schema、笛卡尔积和递归查询，再用 `EXPLAIN (FORMAT JSON)` 读取数据库估算成本。超过 `QUERY_SAFETY_MAX_TOTAL_COST` 或 `QUERY_SAFETY_MAX_PLAN_ROWS` 时只记录“需要审批”，不会执行；审批恢复由 P7 实现。

数据库失败不会把原始异常、主机、账号或密码交给模型，只会反馈稳定的安全错误码。初稿失败后最多修复两次，第三次仍失败即终止。15 道 P2 固定题用于可复现的离线候选执行结果对比；真实供应商模型的质量需要配置 API Key 后另行评测，不能用离线结果冒充。

## 无模型安全纵向切片

该切片使用仓库内固定 SQL 验证完整安全链路，不接收模型生成内容：

```bash
make compose-up
make verify-safety
```

SQL 必须先通过 SQLGlot AST 检查，只允许单条查询、Northwind schema 和元数据快照中的表。写操作、多语句、跨 schema、`SELECT INTO`、行锁和危险函数会在调用执行器之前被拒绝。

通过检查的查询会被外层 `LIMIT` 再次约束，并使用专用只读账号在显式只读事务中执行。返回结果同时受到最大行数、列数和序列化字节数限制。每次成功、策略拒绝或执行失败都会产生只包含指纹、原因码、资源标识和计数的审计事件，不保存 SQL 原文和业务数据行。

当前审计通过 `QueryAuditSink` 边界输出；自动化测试使用内存实现，运行时可使用安全日志实现。将事件持久化到 Java 平台 `audit_events` 表属于 P7 跨服务集成，Python 不直接写平台数据库。

## 端口

| 服务 | 默认端口 |
|---|---:|
| Web | 3000 |
| Java Platform API | 8080 |
| Python Agent Service | 8000 |
| Platform PostgreSQL | 5432 |
| Business PostgreSQL | 5433 |
| Redis | 6379 |
