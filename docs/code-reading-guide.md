# 全项目代码阅读导航

按岗位补课时，配合 [课程 × 代码 × 动手验收](learning/README.md) 与 [逐文件课程索引](learning/file-course-map.md) 使用；本页用于追调用链，学习指南用于选分集、补技术和做练习。

这份文档对应当前维护版代码。Java 已从“按业务模块分包、模块内分层”改成统一按层分包，但整个系统仍由 Web、Java Platform 和 Python Agent 三个应用组成，不是把三种语言合并到一个进程。

## 1. 先运行，再按一条请求读代码

先按 [当前本地启动手册](current-local-startup-guide.md) 启动。已有旧版本环境先看其中第 0 节，清除 Java 旧包编译产物即可，不要删除数据库卷。

接着读 [总体架构](architecture.md)，再看 [Java 平台阅读指南](../platform-api/README.md)。[开发手册](development.md) 用于查验收命令；`stage-*.md` 是阶段性历史记录，不必逐份通读。

## 2. 整个仓库怎么分工

```text
enterprise-data-copilot/
├── web/src/                       用户界面与服务端同源代理
│   ├── app/                       Next.js 页面、健康检查和 API 路由
│   ├── components/                分析工作台与结构化图表
│   └── lib/                       API 调用、SSE、类型与图表策略
├── platform-api/                  单个 Spring Boot 工程，Java 统一按层分包
│   ├── src/main/java/com/example/copilot/
│   ├── src/main/resources/        application.yml 与 Flyway 迁移
│   └── src/test/java/             单元、WireMock 与 Testcontainers 集成测试
├── agent-service/app/             Python 分析工作流
│   ├── agent/                     LangGraph、动作、checkpoint、步骤与审批回调
│   ├── nl2sql/                    选表、生成 SQL 与受限修复
│   ├── query_safety/              确定性 guard、成本估算和只读执行
│   ├── retrieval/                 指标文档解析、混合检索与引用
│   ├── metadata/                  业务库 schema 获取
│   ├── llm/                       模型适配、结构化输出与 Fake LLM
│   └── evaluation/                离线／真实模型评测入口
├── contracts/                     Java 外部 API、Python 内部 API 与事件契约
├── knowledge/                     演示指标文档
├── metadata/                      固定 schema 快照
├── evaluation/                    题集、标准 SQL 与评测报告
├── infra/                         数据库初始化与观测配置
├── scripts/                       固定数据加载、只读边界与交接检查
├── docs/                          当前说明、ADR、阶段历史和演示资料
├── Makefile                       统一启动、构建与验收入口
└── docker-compose*.yml            基础依赖与完整应用栈
```

Java 内部的 `controller/service/repository/entity/dto/task/client/event/config` 各层作用与文件映射见 [Java 目录说明](../platform-api/README.md#1-先看整体目录)。Python 仍按能力模块组织，此次没有迁移 Python 或 Web 目录。

## 3. 第一条线：从登录看到数据库

1. [CopilotApp.tsx](../web/src/components/CopilotApp.tsx)：登录表单与登录后的工作台。
2. [Web API 代理](../web/src/app/api/platform/%5B...path%5D/route.ts)：浏览器请求经同源 `/api/platform/*` 转发至 Java；它不是 Python 入口。
3. [AuthController.java](../platform-api/src/main/java/com/example/copilot/controller/AuthController.java)：Java `/api/auth/login`。
4. [AuthenticationService.java](../platform-api/src/main/java/com/example/copilot/service/AuthenticationService.java)：查租户和用户、验证密码、签发 JWT。
5. [AppUserRepository.java](../platform-api/src/main/java/com/example/copilot/repository/AppUserRepository.java) 与 [AppUser.java](../platform-api/src/main/java/com/example/copilot/entity/AppUser.java)：平台库访问与实体。

权限入口在 [SecurityConfiguration.java](../platform-api/src/main/java/com/example/copilot/config/SecurityConfiguration.java)，演示账号初始化在 [DevelopmentBootstrap.java](../platform-api/src/main/java/com/example/copilot/config/DevelopmentBootstrap.java)。不要在 Controller 中寻找数据库密码或模型 Key。

## 4. 第二条线：从分析问题看到最终结果

先追主干，不必一次读懂全部策略：

1. [AnalysisJobController.java](../platform-api/src/main/java/com/example/copilot/controller/AnalysisJobController.java) 接收任务，调用 [AnalysisJobService.java](../platform-api/src/main/java/com/example/copilot/service/AnalysisJobService.java) 校验租户、数据源和幂等键，保存任务并返回 `202`。
2. 事务提交后，[AnalysisJobDispatcher.java](../platform-api/src/main/java/com/example/copilot/task/AnalysisJobDispatcher.java) 调度 [AnalysisJobWorker.java](../platform-api/src/main/java/com/example/copilot/task/AnalysisJobWorker.java)；Worker 通过 [HttpAgentRunClient.java](../platform-api/src/main/java/com/example/copilot/client/agent/HttpAgentRunClient.java) 调用 Python。
3. Python 从 [agent/api.py](../agent-service/app/agent/api.py) 进入 [agent/service.py](../agent-service/app/agent/service.py)；[agent/graph.py](../agent-service/app/agent/graph.py) 定义工作流，[agent/actions.py](../agent-service/app/agent/actions.py) 执行检索、生成和安全查询动作。[agent/factory.py](../agent-service/app/agent/factory.py) 负责把生产依赖组装起来。
4. 想看 SQL 为什么被允许／拒绝，读 [query_safety/guard.py](../agent-service/app/query_safety/guard.py)；想看实际业务查询，读 [query_safety/executor.py](../agent-service/app/query_safety/executor.py)；想看文字结果和图表，读 [agent/answering.py](../agent-service/app/agent/answering.py) 与 [agent/charting.py](../agent-service/app/agent/charting.py)。
5. Python 返回结构化结果后，Java Worker 将最终结果保存到平台 PostgreSQL。实时进度通过 [AnalysisEventStreamService.java](../platform-api/src/main/java/com/example/copilot/service/AnalysisEventStreamService.java) 与 Redis 传给前端；Web 的 [sse.ts](../web/src/lib/sse.ts) 解析事件，[StructuredChart.tsx](../web/src/components/StructuredChart.tsx) 展示受限图表。

Python 保存步骤和申请审批是另一方向：`agent/steps.py` → Java [InternalAgentCallbackController.java](../platform-api/src/main/java/com/example/copilot/controller/InternalAgentCallbackController.java)。Java 的 `client/agent` 是出站客户端，不是这些入站回调的 Controller。

## 5. 看代码时容易混淆的地方

- Java Repository 读写的是平台库；Northwind 业务查询由 Python 专用只读执行器完成。
- 当前只支持与部署配置完全匹配的固定 Northwind 演示源，不是任意数据源动态连接框架。
- `dto/request`、`dto/response` 是 API 字段；`entity` 是持久化对象；`enums` 是状态／角色，不能只按名称相似就互换。
- 创建任务返回 `202` 只表示已接收，不代表 SQL 已执行成功。最终状态以 Java 中的任务记录为准。
- `/health` 成功不等于模型可用，也不等于已跑完 Web 端到端测试。
- 阶段文档中的旧测试数量和“留给后续阶段”是当时记录；当前启动看启动手册，当前目录看本指南和 Java README。

## 6. 改完代码去哪里验证

从根目录查 [Makefile](../Makefile) 与 [开发手册](development.md)。Java 全量构建与回归：

```bash
(cd platform-api && ./mvnw --batch-mode clean verify spotless:check)
```

Docker 必须运行，因为集成测试使用临时 PostgreSQL／Redis；这些测试不需要真实模型 Key。接口或任务状态有变化时，还要运行 `make contract-test`；整项目验收用 `make verify-all`，不要把一次 Java 启动检查当成整项目回归。
