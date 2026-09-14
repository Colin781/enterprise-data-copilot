# 阶段一实施与验证记录

## 本阶段目标

建立可重复构建的 Java、Python、Web 三服务骨架，以及本地依赖、迁移基线、契约、统一命令和 CI。阶段一不包含业务数据、鉴权、Agent、Prompt 或 NL2SQL。

## 分步产出

1. **Java Platform API**
   - Java 21、Spring Boot 4.1.1、Maven Wrapper。
   - Web MVC、Actuator、Validation、JPA、Flyway 和 PostgreSQL 驱动。
   - `/health`、Flyway V1 基线、H2 测试配置和 Spotless。
   - 任务状态枚举、确定性状态迁移规则和幂等重复更新语义。
2. **Python Agent Service**
   - Python 3.12、uv、FastAPI、Pydantic Settings 和 Uvicorn。
   - `/health`、ASGI HTTP 测试、Ruff 和 `uv.lock`。
3. **Web**
   - Next.js 16.2.11、React 19、TypeScript、App Router。
   - 阶段状态首页、`/health`、ESLint、类型检查和 `pnpm-lock.yaml`。
   - pnpm 依赖构建采用显式 allowlist，只允许 `sharp` 与 `unrs-resolver`。
4. **本地基础设施**
   - pgvector/PostgreSQL 17 平台库。
   - 独立 PostgreSQL 17 业务库。
   - Redis 8.2；三个依赖均配置健康检查和持久卷。
   - 业务库管理员与只读查询账号分离；只读账号初始化可幂等重放。
5. **工程入口**
   - `.env.example`、Makefile、两个 OpenAPI 3.1 合约和任务事件 JSON Schema。
   - GitHub Actions 分别运行 Java、Python、Web、契约和基础设施检查。

## 本地验证结果

| 检查 | 结果 |
|---|---|
| Java JUnit + Spring context | 8 passed |
| Flyway 测试迁移 | V1 成功应用到 H2 |
| Java Spotless | passed |
| Python pytest | 9 passed；包含 OpenAPI、事件 Schema、服务边界与跨语言状态一致性 |
| Python Ruff lint/format | passed |
| Web ESLint | passed |
| Web TypeScript | passed |
| Web production build | passed；`/` 静态生成，`/health` 动态路由 |
| Compose 配置解析 | passed |
| 业务库只读账号 | `SELECT` 成功；默认事务只读；`CREATE TABLE` 被拒绝 |
| Platform PostgreSQL | healthy |
| Business PostgreSQL | healthy |
| Redis | healthy |
| Java `/health` | HTTP 200，状态 `UP` |
| Python `/health` | HTTP 200，状态 `UP` |
| Web `/health` | HTTP 200，状态 `UP` |
| Java + PostgreSQL 实际启动 | Flyway V1 成功应用到 PostgreSQL 17 |

GitHub Actions 工作流已经生成，但仓库尚未提交和推送，因此远程 CI 尚未实际执行。上表只记录本地运行结果。

## 阶段退出判断

- [x] 三个服务均提供 `/health`。
- [x] 两个 PostgreSQL 与一个 Redis 可通过 Compose 启动并达到 healthy。
- [x] `.env` 被忽略，模板不包含真实密钥。
- [x] Java、Python 和 Web 均有可重复的依赖/Wrapper 基线。
- [x] Java 状态机、Platform/Agent API 和事件契约使用一致的任务状态。
- [x] 业务数据库具有独立只读角色，并有可执行的写入拒绝验证。
- [x] 本地执行了 CI 中对应的测试、静态检查和构建命令。
- [x] P1 验收结束时未提前混入阶段二及后续业务功能。

阶段一本地代码验收可以结束；远程 CI 仍需在首次提交和推送后确认。后续 P2 结果单独记录在 `docs/stage-2-data-metadata.md`。
