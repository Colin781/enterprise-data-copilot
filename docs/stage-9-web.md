# P9 前端与端到端操作闭环验收记录

## 本阶段目标

将 P3～P8 已验证的后端能力收敛为一个可操作、可恢复、不会执行模型代码的租户分析界面。P9 只完成产品操作闭环，不提前伪造 P10 的模型质量数字或 P11 的 P95、Token 与成本指标。

## 已实现页面

1. **登录**：租户标识、邮箱和密码登录；JWT 仅保存在当前标签页 `sessionStorage`，过期或服务端返回 401 时清除会话。
2. **分析工作台**：选择数据源、提交问题、查看最近 50 个有权限的任务。创建仍立即返回 `202`，页面同时使用带 Bearer Token 的 fetch SSE 和三秒 PostgreSQL 状态轮询恢复进度。
3. **结果切换**：结论、最多 100 行的分页数据表、结构化图表和只读 SQL 四个标签。SQL 复制必须经过风险提示。
4. **执行轨迹**：按服务端顺序展示脱敏 Agent 步骤、状态、重试次数、耗时和稳定错误码，不展示完整节点输入、模型提示词或敏感结果。
5. **审批中心**：管理员查看当前租户审批记录，并对待审批查询做一次性批准或拒绝；普通角色看不到入口，服务端仍独立执行 RBAC。
6. **数据源管理**：所有角色可查看租户数据源；只有管理员可登记。浏览器和 API 响应看不到主机凭据，输入只接受 `env/vault/secret` 引用。
7. **指标文档管理**：管理员上传有界 Markdown/PDF；Java 校验身份并调用 Python 内部索引接口，Python 执行 P6 已验证的解析、版本替换、分块和 pgvector/FTS 入库。
8. **管理概览**：只汇总当前租户可证实的数据源、文档、任务和审批数量。P95 和模型成本明确标注为 P11 待接入，不以前端估算冒充观测指标。
9. **可重复本地演示**：显式 `PLATFORM_BOOTSTRAP_ENABLED` 开关可幂等创建本地 Northwind 租户、管理员、分析员和只读数据源；默认配置只用于本地，非开发环境必须关闭。

## 安全与体验边界

- 浏览器只调用 Next.js 同源代理；代理目标由服务端固定 `PLATFORM_API_URL` 指定，不能由请求参数控制，也不会把 Agent Service 暴露给浏览器。
- 图表只接受 `bar/line/pie/table` 四种数据规范，横轴和 series 必须来自返回列，最多三个 series；使用 React SVG 映射，不使用 `eval`、`Function`、动态脚本或原始 HTML。
- 长任务显示明确状态、执行秒数和最后更新时间；超过 30 秒提示任务仍在受控执行，可离开后返回，不使用无信息的无限转圈。
- 表格每页 20 行；达到 100 行时提示结果可能已按安全上限截断。图表最多绘制前 30 行。
- 错误只展示稳定错误码、行动建议和 trace ID，不显示 Java/Python 堆栈。
- 文档上传在浏览器、Java 和 Python 三层设置类型/编码/大小约束，内容不会回传到列表响应。

## 后端最小支撑

- Flyway V5 在 `analysis_jobs` 增加 columns、rows、chart spec、citations 的 JSON 持久化字段；PostgreSQL 继续是最终结果权威源。
- 增加租户/所有者过滤的任务列表、管理员审批列表，以及管理员指标文档上传与租户文档列表。
- Python `compose` 节点从已限制的结果列/行确定性生成 `ChartSpec`，不要求模型生成或执行绘图代码。

## 验收命令

```bash
make verify-p9
```

该命令使用仓库已安装的本地 Next/TypeScript/ESLint 二进制，避开离线环境下 pnpm 的签名元数据查询，同时执行：

- 结构化图表 allowlist、SSE 解析和无动态代码执行扫描；
- Web ESLint、TypeScript 和 Next.js production build；
- Java 的登录/RBAC/租户边界、文档上传、异步结果持久化和 SSE 集成测试；
- Python 的图表规范、文档上传边界与 OpenAPI 契约测试。

完整 Java/Python 回归仍应在交付前分别执行 `./mvnw test` 与启用 P2～P7 数据库开关的 `uv run pytest`。远程 GitHub Actions 只有在提交推送后才能作为远程证据。

2026-09-18 P9 收口实测结果：

- `make verify-p9`：Web 3 项安全/协议测试、Java 11 项 P9 关联集成测试、Python/契约 14 项，全部通过；
- Java 全量回归：19 passed，无失败、错误或跳过；Flyway V1～V5 均从空 PostgreSQL 应用成功；
- Python 全量联合回归：130 passed；P2、安全纵切、P5、P6、P7 数据库开关全部启用，无跳过项；
- OpenAPI 与事件契约：12 passed；
- Web ESLint、TypeScript、Next.js 16.2.11 production build 与 3 项前端测试全部通过；
- Java Spotless、Python Ruff、`uv sync --locked --all-groups --offline` 和 Compose 配置检查全部通过；
- 未调用 `pnpm`；离线验证继续使用仓库锁定且已安装的本地 Node 二进制。

本次收口还修复了一个测试隔离缺陷：内部知识上传和 Agent API 测试不再假设示例服务令牌，而是通过 FastAPI dependency override 注入独立测试令牌，因此用户在 `.env` 中设置随机 `AGENT_WORKFLOW_SERVICE_TOKEN` 后，验收结果不会再受个人环境配置影响。README 核心演示与手工验收问题也已统一为固定数据真实覆盖的 2024～2025 年口径；1997 年仅保留在故障记录中用于解释“查询成功但结果为空”的数据边界。

## 明确留给后续阶段

- P10：50+ NL2SQL、20+ RAG 的完整真实模型评测、失败分类和端到端成功率；
- P11：OpenTelemetry、Prometheus、P95、Token/成本和故障演练；
- P12：正式截图、演示视频和可追溯简历数字。
