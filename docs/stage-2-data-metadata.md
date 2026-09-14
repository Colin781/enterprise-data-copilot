# P2 数据与元数据验收记录

## 本阶段完成了什么

P2 采用收敛版路线，只完成后续安全纵向切片真正依赖的数据基础，不提前实现 P3 的登录、租户和平台数据源管理。

1. **固定数据**：仓库内置 `northwind-compact-v1`，包含 8 张业务表、10 个客户、12 个商品、20 张订单和 40 条订单明细。建表与装载脚本可重复运行。
2. **数据库硬隔离**：应用查询账号默认事务只读，默认 `search_path` 为 `northwind`，只能查询该 schema，且语句最长运行 2 秒。
3. **元数据读取**：Python 从 PostgreSQL 提取表、列、类型、可空性、表/字段注释、主键和外键；不提取业务样例行。
4. **版本与缓存**：数据集有固定版本号，schema 摘要有 SHA-256 版本；内存缓存具有可配置 TTL，也支持主动失效。
5. **评测种子**：首批 15 条中文问题均配有 gold SQL、预期列名和能力标签。

## 主要文件

| 内容 | 位置 |
|---|---|
| Northwind 表结构 | `infra/docker/business-db/init/010-northwind-schema.sql` |
| 固定数据 | `infra/docker/business-db/init/020-northwind-data.sql` |
| 只读角色 | `infra/docker/business-db/init/090-create-readonly-user.sh` |
| 数据源连接边界 | `agent-service/app/data_sources/` |
| schema introspection 与缓存 | `agent-service/app/metadata/` |
| 固定元数据快照 | `metadata/northwind-schema-v1.json` |
| 首批评测题 | `evaluation/northwind/gold-v1.jsonl` |
| 真实数据库测试 | `agent-service/tests/test_p2_integration.py` |

## 本地验收证据

执行 `make verify-p2` 的结果：

- 只读账号 `SELECT` 成功。
- `CREATE TABLE` 返回只读事务错误。
- 查询 `restricted.private_notes` 返回 schema 权限错误。
- `pg_sleep(3)` 被 2 秒 `statement_timeout` 取消。
- 实时 introspection 结果与提交的 SHA-256 版本快照完全一致。
- 15 条 gold SQL 均执行成功，返回列与评测定义一致。
- P2 真实 PostgreSQL 集成测试：5 passed。

此外，Python 普通测试为 18 passed、5 skipped；5 个跳过项正是需要通过 `make verify-p2` 单独启用的真实数据库测试。Java 8 个测试继续通过，Web lint 与类型检查继续通过。

## 明确留给后续阶段

- P3：JWT、租户隔离、数据源登记 API 与平台库持久化。
- 安全纵向切片/P5：SQL AST、表字段 allowlist、强制 LIMIT、结果大小限制和审计执行器。
- P6：把本阶段的 schema 摘要接入检索；当前没有发送给任何模型。
- P10：把 15 条 gold case 持续扩充到 50 条以上，并建立 execution accuracy 报告。

远程 GitHub Actions 仍需在仓库首次提交并推送后确认；当前结论只陈述已经执行过的本地证据。
