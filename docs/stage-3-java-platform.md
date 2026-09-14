# P3 Java 业务平台验收记录

## 本阶段完成了什么

P3 按收敛版路线建立 Java 平台的企业业务边界。浏览器可以登录、登记数据源元数据、创建分析任务和读取任务状态；租户与用户身份只能来自平台签发的 JWT，不能由请求正文自行指定。

1. **密码登录与 JWT**：密码使用 BCrypt 校验；访问令牌包含 `sub`、`tenant_id` 和 `roles`，默认 30 分钟过期，并校验签发者和有效期。
2. **RBAC**：`ADMIN` 可以登记数据源；`ADMIN` 和 `ANALYST` 可以创建任务；`VIEWER` 不能创建任务。
3. **租户隔离**：所有数据源和任务查询都显式带当前 `tenant_id`。访问其他租户资源统一返回 404，避免泄露资源是否存在。
4. **平台实体**：Flyway V2 建立租户、用户、角色、数据源、分析任务、审批和审计表。
5. **幂等任务创建**：幂等键按“租户 + 用户”隔离；同一键和同一请求返回原任务，同一键换请求内容返回 409。
6. **并发保护**：任务创建通过用户行锁串行化同一用户的幂等判断；可修改实体使用 `@Version` 乐观锁，过期版本更新会失败。
7. **统一错误结构**：401、403、404、409、422 和 500 都返回稳定错误码、公开消息、时间和 `trace_id`，不返回堆栈、数据库连接串或密钥。
8. **审计**：登记数据源和创建任务会在同一数据库事务中写入审计事件。

## 已实现的接口

| 接口 | 权限 | 作用 |
|---|---|---|
| `POST /api/auth/login` | 公开 | 使用租户、邮箱和密码换取 JWT |
| `GET /api/data-sources` | 已登录 | 只列出当前租户的数据源摘要 |
| `POST /api/data-sources` | ADMIN | 登记数据源元数据和密钥引用 |
| `POST /api/analysis/jobs` | ADMIN、ANALYST | 使用幂等键创建租户内分析任务 |
| `GET /api/analysis/jobs/{jobId}` | 已登录 | 管理员读取租户内任务，其他用户只读取自己创建的任务 |

数据源返回值故意不包含主机地址和 `secret_ref`。登记接口只接受 `env:`、`vault:` 或 `secret:` 形式的密钥引用，不接受数据库密码字段。

## 数据库结构

Flyway V2 新增：

- `tenants`
- `app_users`
- `user_roles`
- `data_sources`
- `analysis_jobs`
- `approvals`
- `audit_events`

外键、唯一约束、状态检查约束、租户查询索引和乐观锁版本列都由迁移脚本定义。Hibernate 使用 `ddl-auto=validate`，只负责检查实体与迁移是否一致，不会在启动时擅自修改表结构。

## 本地验收证据

Java 完整测试结果为 `13 passed`：

- 6 个任务状态机测试。
- 1 个健康检查测试。
- 6 个 Testcontainers + PostgreSQL 17 集成测试。

真实 PostgreSQL 集成测试覆盖：

- Flyway V1、V2 从空库成功执行。
- 未登录访问受保护接口返回 401。
- 错误密码返回统一 401，且不暴露账号是否存在。
- ANALYST 不能登记数据源，VIEWER 不能创建任务。
- 租户 A 不能使用或读取租户 B 的数据源和任务。
- 请求正文伪造 `tenant_id` 会被拒绝。
- 同一幂等键重复提交只产生一条任务和一条审计记录。
- 同一幂等键对应不同内容返回 409。
- 两个并发版本修改同一数据源时，旧版本被乐观锁拒绝。
- 数据源返回中不包含主机和密钥引用。

另外还在本机现有 `platform-db` 上实际启动 Java 服务：Flyway 将 `copilot` schema 从 V1 升级到 V2，`/health` 返回 HTTP 200，匿名访问 `/api/data-sources` 返回 HTTP 401。验证完成后 Java 进程已正常停止。

OpenAPI 合约已同步加入登录和数据源接口；Python 合约测试共 9 项通过。

### 最终全量复检（2026-09-14）

- `./mvnw spotless:check package` 构建成功：Java 13 项测试全部通过，生成可运行 JAR。
- Python 全量测试为 19 项通过、5 项按设计跳过；跳过项是需要显式连接真实业务数据库的 P2 集成测试，之前已单独通过真实数据库验收。
- Python Ruff 代码检查与格式检查均通过。
- Web ESLint 和 TypeScript 类型检查均通过。
- `docker compose --env-file .env.example config --quiet` 通过，Compose 配置有效。
- Testcontainers 临时 PostgreSQL 已自动清理，8080 端口没有残留 Java 服务。
- 三个长期依赖容器 `platform-db`、`business-db`、`redis` 当前均为正常停止状态（`Exited (0)`）；后续联调前可用 `docker compose up -d` 启动。

### P3 复检时的文件状态

P3 验收时仓库尚未创建第一次 Git 提交，因此当时的 115 个项目文件全部是未跟踪文件，而不是“已提交文件上的修改”。本地真实 `.env`、构建目录、虚拟环境、`node_modules` 和 `.DS_Store` 均已被忽略，没有进入待提交列表。远程 CI 也要等首次提交并推送后才能执行。

## 明确留给后续阶段

- 初始租户和管理员由部署或测试夹具在系统外配置；当前没有开放匿名注册接口。
- 数据源登记当前只保存安全的连接元数据和密钥引用；实际连接测试使用 P2 的 Python 能力，跨服务串联留到 Agent 集成阶段。
- `approvals` 已有表和实体，审批创建、批准、拒绝以及状态机联动留到 P7。
- Java 目前只创建 `CREATED` 任务，不调用模型，也不生成或执行 SQL。
- SQL AST、表字段白名单、结果限制和执行审计属于下一步“无模型安全纵向切片”与 P5。
- Python Provider 与结构化模型输出属于 P4。

远程 GitHub Actions 仍需在仓库首次提交并推送后确认；本文件只记录已经实际运行过的本地结果。
