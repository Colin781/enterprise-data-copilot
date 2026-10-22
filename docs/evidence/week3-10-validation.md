# 第 3～10 周改造验证记录

验证日期：2026-10-22（Asia/Shanghai）。

## 已通过

| 范围 | 结果 | 证据 |
| --- | --- | --- |
| Python 全套 | 213 passed | 包括原有业务/安全/评测、真实 pgvector、Neo4j、PostgreSQL Checkpointer、MCP 协议、抽取和接口契约 |
| Python 静态检查 | 全部通过 | `ruff check app tests` |
| Java 全套 | 64 项，0 failure/error | `platform-api/target/surefire-reports`；Testcontainers 隔离数据库 |
| Web | 7 项测试、类型检查、ESLint 通过 | `pnpm test/typecheck/lint` |
| Web 生产构建 | 通过 | Next.js 生产构建 |
| Docker 镜像 | Java/Python/Web 全部构建成功 | 最终 Compose 构建 |
| 完整启动 | 所有应用及 PostgreSQL/Redis/Neo4j 健康 | 本地 Compose，Web 端口 3100 |
| 实际跨服务联调 | 10 项通过、0 模型调用 | `week3-10-smoke.json` |

## 实测报告

- `evaluation/northwind/week3-query-plans.json`：10 万行临时合成数据，优化前后真实执行计划；2.583 ms → 0.346 ms，不能作为生产接口加速结论。
- `evaluation/northwind/week5-retrieval-offline.json`：24 条样本、四种检索模式，哈希 Embedding + 词重叠重排；记录拒答与检索失败，不代表真实语义模型评测。
- `evaluation/northwind/week7-extraction-offline.json`：3 条人工标注样本的 Gold Replay；只验证结构、证据和图写入流程，不代表模型抽取 F1。
- `docs/evidence/week3-10-smoke.json`：健康、登录、匿名拒绝、图检索、关键词检索、MCP 初始化/列表/实际目录工具/资源读取。

## 验证范围与限制

1. 模型 HTTP 适配器用模拟服务器测试排序、维度、归一化、错误分类和重试。未调用实际付费 Embedding/Reranker，也未宣称已测量真实模型答案准确率。
2. 图谱实际 Neo4j 测试覆盖幂等替换、邻居查询、最短路径、截断和租户隔离。GraphRAG 的 LLM 回答使用受控测试输出验证引用 ID；真实业务语义正确性仍需人工评审。
3. Python 全量测试在本次新建的临时样本数据库中执行。安全测试里的 DELETE 是必须被拦截的输入，断言执行器调用次数为零。最初针对现有环境的执行被自动审批阻止，之后改在隔离数据库中完成验收。
4. 临时测试容器在验证后停止；主项目服务保留运行，用户原有数据库卷保留。
5. 宿主机 3000 端口已有另一个 Node 应用，本项目忽略提交的 `.env` 已设置 `WEB_PORT=3100` 和 `WEB_HTTP_PORT=3100`，未终止该其他应用。
6. 工作区原有未提交改动保留，未创建提交。原有两个 Java 文件末尾空行的 diff 警告未作为本次功能改动处理。
7. Starlette TestClient 有一条依赖弃用警告；没有测试失败。

## 复现

日常命令见 `docs/weeks-3-10-upgrade.md`。运行实际只读联调：

```bash
cd agent-service
uv run python -m app.evaluation.upgrade_smoke \
  --web-url http://localhost:3100 --output ../docs/evidence/week3-10-smoke.json
```

该工具读取 `.env` 中的本地演示账号，令牌和密码只保存在内存，不写进报告。更换过账号密码的环境可通过单独的环境配置文件与 `--env` 参数运行。
