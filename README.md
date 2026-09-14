# Enterprise Data Copilot

面向零售经营分析的、可控且可审计的企业数据与指标知识分析 Agent。

业务分析员可以用自然语言查询 Northwind 零售数据。系统结合数据库元数据与指标定义生成只读 SQL，在执行前完成确定性安全检查，并返回可追溯的文字结论、表格、图表规范、SQL 与引用。它不是一个可以任意操作数据库的通用 Agent。

> 当前状态：P0～P5 和无模型安全纵向切片已完成本地验收；系统已能把自然语言转换为结构化分析计划和 SQL，并在列级权限、成本门槛、只读执行与有限修复约束下运行。

## 核心演示

1. 分析员询问“1997 年每季度销售额和环比变化是多少？”
2. 系统展示规划、指标检索、SQL 生成、安全检查、执行和分析步骤。
3. 结果包含口径引用、只读 SQL、数据表与结构化图表规范。
4. 对“删除所有订单”等危险请求，在 SQL 执行前明确拒绝并留下审计记录。

## 产品边界

- 主场景：零售经营分析。
- 主评测数据集：Northwind；Chinook 仅用于迁移验证。
- 数据访问：只读 PostgreSQL；不支持写入客户数据库。
- 服务职责：Java 负责身份、租户、权限、任务、审批和审计；Python 负责检索、规划、NL2SQL、安全校验与结果解释。
- 模型权限：模型不能绕过 SQL AST 规则、数据库只读账号、查询超时和结果上限。

## 项目文档

- [第一阶段小结：P0～P2](docs/milestone-1-foundation-summary.md)
- [产品需求](docs/product-requirements.md)
- [总体架构](docs/architecture.md)
- [Java/Python 服务边界 ADR](docs/adr/0001-java-python-boundary.md)
- [手工验收问题与拒绝场景](docs/manual-acceptance.md)
- [实施计划审视](docs/implementation-roadmap.md)
- [阶段一实施与验证记录](docs/stage-1-foundation.md)
- [阶段二数据与元数据验收记录](docs/stage-2-data-metadata.md)
- [阶段三 Java 业务平台验收记录](docs/stage-3-java-platform.md)
- [阶段四模型适配与结构化输出验收记录](docs/stage-4-llm-provider.md)
- [固定 SQL 安全纵向切片验收记录](docs/stage-safety-vertical-slice.md)
- [阶段五安全 NL2SQL 验收记录](docs/stage-5-safe-nl2sql.md)

## 计划技术栈

- Web：React / Next.js + TypeScript
- Platform API：Java 21 + Spring Boot + Spring Security + Flyway
- Agent Service：Python 3.12 + FastAPI + LangGraph + Pydantic + SQLGlot
- 数据：PostgreSQL + pgvector、独立只读业务 PostgreSQL、Redis
- 验证：JUnit、pytest、Testcontainers、Playwright、NL2SQL/RAG 评测集

## 当前里程碑

| 阶段 | 状态 | 退出条件 |
|---|---|---|
| P0：题目和证据 | 已完成初版 | 场景、边界、架构决策和验收样例可评审 |
| P1：本地环境和骨架 | 已完成本地验收 | 三个服务健康检查、依赖可一键启动、本地 CI 等价命令通过 |
| P2：固定数据、元数据与只读边界 | 已完成（本地） | 真实 PostgreSQL 的 5 项集成测试通过 |
| P3：Java 身份、租户与任务平台 | 已完成（本地） | 13 个 Java 测试通过，其中 6 个使用真实 PostgreSQL |
| P4：模型适配与结构化输出 | 已完成（本地） | Fake LLM、非法 JSON 重试和超时分类测试通过 |
| 无模型安全纵向切片 | 已完成（本地） | 固定 SQL 贯通 guard、只读执行、结果限制和审计；危险 SQL 到达执行器 0 次 |
| P5：安全 NL2SQL | 已完成（本地） | 相关表选择、结构化生成、列级白名单、成本检查、最多两次修复和阶段性 execution accuracy 均有自动化证据 |
| P6+ | 未开始 | 按实施路线逐阶段验收 |

## 本地启动

需要 Java 21、Python 3.12 + uv、Node.js 22+ + pnpm 11，以及 Docker。

```bash
make env
make compose-up
make setup
make dev
```

健康检查：

- Web：`http://localhost:3000/health`
- Platform API：`http://localhost:8080/health`
- Agent Service：`http://localhost:8000/health`

完整开发说明见 [docs/development.md](docs/development.md)。

## License

[MIT](LICENSE)
