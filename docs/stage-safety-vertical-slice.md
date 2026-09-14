# 固定 SQL 安全纵向切片验收记录

## 目标

在接入模型生成 SQL 之前，先用一条固定 Northwind 查询贯通确定性检查、只读执行、结果限制和审计。这样后续 P5 出现问题时，可以明确区分是模型质量问题还是安全与数据库基础设施问题。

## 已实现的防线

1. **SQL AST 检查**：SQLGlot 使用 PostgreSQL 方言解析，无法解析或包含多条语句时直接拒绝。
2. **只允许查询**：根节点必须是 Query；DDL、DML、COPY、事务命令、`SELECT INTO` 和 `FOR UPDATE/SHARE` 均拒绝。
3. **资源白名单**：物理表只能来自固定元数据快照，显式 schema 只能是 `northwind`；CTE 名称与物理表分开处理。
4. **函数正向识别**：只允许 SQLGlot 能明确识别的内置表达式；`pg_sleep`、文件读取、dblink、序列修改、配置修改和所有未识别的自定义函数全部拒绝。
5. **强制结果上限**：安全查询外层增加 `LIMIT max_rows + 1`，用于可靠判断是否截断。
6. **数据库纵深防御**：只使用 `northwind_reader`，显式开启只读事务，并在事务内设置 statement timeout。
7. **返回限制**：限制最大行数、列数和 JSON 序列化字节数；重复列名也拒绝，避免结构歧义。
8. **审计闭环**：成功、策略拒绝、执行失败都生成版本化审计事件。事件包含租户、用户、任务、数据源、trace、SQL 指纹、原因码和结果计数，不包含 SQL 原文或结果行。
9. **审计失败即失败**：审计端口无法记录时，不向上层返回成功结果。

## 固定验收 SQL

固定查询计算 Northwind 销售额最高的五个客户，涉及 `customers`、`orders` 和 `order_details` 三张表。它不是模型生成内容，定义在 `app/query_safety/fixed.py`。

## 自动化证据

单元测试验证：

- 固定 SQL 会被标准化、加结果上限、执行一次并审计一次。
- 空 SQL、词法错误、DELETE、多语句、`SELECT INTO`、行锁、跨 schema、未知表、`pg_sleep` 和未知自定义函数全部拒绝。
- 所有危险 SQL 的执行器调用次数都是 0。
- CTE 可以引用白名单内物理表，但 CTE 名不会被误判为外部表。
- 执行失败与审计失败均返回稳定且不泄密的错误。
- 行数与字节数限制会截断结果，结果对象的 repr 不包含业务行。
- 阈值由 `QUERY_SAFETY_*` 环境变量集中配置。
- P2 的 15 条 gold SQL 全部能通过当前确定性 guard，避免安全规则误伤既有正确基线。

真实 PostgreSQL 集成测试验证：

- 固定 SQL 使用只读账号成功返回五行、两列，并生成成功审计。
- 真实结果受行数和字节数双重限制。
- 超过列数限制时执行结果不返回，并生成失败审计。
- DELETE、跨 schema 和 `pg_sleep` 到达真实执行器的次数均为 0。

最终本地结果：

- `make verify-safety` 共 23 项测试全部通过，其中 6 项直接连接真实 PostgreSQL。
- Python 默认全量回归 53 项通过、11 项按设计跳过；跳过项由 P2 和本安全切片的显式数据库验收命令覆盖。
- `make verify-p2` 的 5 项真实数据库测试重新通过，只读写入拒绝、跨 schema 拒绝和 statement timeout 均正常。
- Ruff 检查与格式检查、Java 13 项测试、Web ESLint/TypeScript、Compose 配置和依赖锁检查全部通过。

运行命令：

```bash
make compose-up
make verify-safety
```

## 后续边界

- 本切片不接受模型 SQL；P5 才会把结构化模型输出接到 guard 前面。
- 完整列级 allowlist、成本 `EXPLAIN`、高成本审批和最多两次 SQL 修复属于 P5/P7。
- `QueryAuditSink` 已预留平台落库边界；Java 持久化接线属于 P7，Python 不直接写平台数据库。
