# 岗位导向：课程 × 代码 × 动手验收

核对日期：2026-10-22。对应主项目功能提交 `1c586bd`。本指南不要求你重新生成一遍项目，而是把现有工程变成你能解释、调试和维护的作品。

## 从这里开始

- 本页：按 L01 → L16 学习，知道每一步看什么、读什么、做到什么程度。
- [逐文件课程索引](file-course-map.md)：从某个文件反查课程、技术和阅读目标，覆盖应用源码、测试、迁移、配置、脚本及数据材料。
- [精确分集观看清单](course-watchlist.md)：五门课哪些集必看、选看、暂缓，链接可直接跳到对应 P。
- [已核对课程目录](course-catalog.json)：五门课全部 373 集的标题、时长和来源，方便核验 P 号。
- [资料核对记录](validation.md)：文件覆盖、链接检查、课程验证边界与测试说明。
- [当前启动手册](../current-local-startup-guide.md)、[请求调用链](../code-reading-guide.md)、[第 3～10 周交付手册](../weeks-3-10-upgrade.md)：分别解决运行、导航、改造验收问题。

验证边界：核对了 B 站公开元数据中的标题、分集号和时长，**没有逐集观看视频**，因此“适用”是根据分集标题和本项目代码作出的学习安排，不是对讲师每段内容的背书。页面受访问限制时使用同站公开视频信息接口；完整目录不是字幕或逐字稿。

### 先做三天，不要先连看几十小时

1. 第一天：按启动手册跑通登录和一次分析。画出 Web → Java → Python → PostgreSQL 的箭头；读 L01 的三处入口，解释谁创建对象、谁调用谁。
2. 第二天：学 L02，追一次成功和一次失败的 HTTP 请求；在本地练习分支补一个输入校验测试，不重构整个 Controller。
3. 第三天：学 L03，追“筛选任务”从参数到 XML SQL 的全过程；写出绑定参数后的查询形状，补一条租户/用户隔离测试。

三天后再进入索引、RAG 和 Agent。不会 Java 基本语法时先停在 L01，不要一边查泛型一边硬读审批恢复。

## 优先级与岗位关系

| 岗位要求 | 学习单元 | 必须能做的事 |
|---|---|---|
| Java / Spring Boot / MyBatis，检索筛选与后台接口 | L01–L05 | 独立写一个带校验、事务、权限、分页的业务接口并测试 |
| SQL / PostgreSQL / 查询优化 | L03–L04、L10 | 写 JOIN/聚合/窗口函数；读 EXPLAIN；说明只读执行边界 |
| 模型 API / Prompt / 结构化输出 / RAG | L07–L10 | 解释从文档到引用答案；定位检索错还是生成错 |
| Agent / 工作流 / 任务编排 | L06、L11–L12 | 解释状态、分支、重试、审批和重启恢复 |
| 知识图谱 / GraphRAG / 关系网络 | L13、L15 | 从原文抽取带证据的关系，检索租户子图并展示 |
| MCP 加分项 | L14 | 演示握手、tools/list、tools/call 与越权拒绝 |
| 前后端联调、Docker / Git / Linux、质量与稳定性 | L02、L15–L16 | 看请求、日志与测试定位问题，能部署和回滚自己的提交 |

建议学习时间比例：课程 30%，读项目和画链路 30%，自己改小功能与测试 40%。课看完不等于掌握；下面每单元的验收才是升级条件。L01–L12、L15–L16 是主干，L13–L14 是加分能力；时间紧时先把主干讲明白。

## 学习规则与版本差异

1. 每个单元只先看指定分集，然后回到指定文件。相同 P 在不同单元出现时不必重看，可查笔记。
2. Spring 是 IoC、事务、MVC 等基础能力；Boot 在此基础上提供自动配置、依赖和运行约定。岗位要求 Boot 并不意味着可跳过构造器注入、Bean 和事务；但不用通刷旧 XML 章节。
3. 本项目 Java 21 / Spring Boot 4.1.1。老课的依赖版本、`javax.*`、JUnit 4、旧安全配置和 XML 配置方式不直接复制；以 [pom.xml](../../platform-api/pom.xml)、锁文件和当前官方文档为准。
4. 本项目保留 JPA 实体/Repository，同时增加 MyBatis XML 查询。依赖包含 MyBatis-Plus，**不等于代码已使用 BaseMapper、LambdaQueryWrapper、逻辑删除或 MP 乐观锁插件**。不要把选修课内容写成现有项目经历。
5. RAG 课用 LangChain/向量库封装；项目使用自定义 provider、Pydantic、PostgreSQL/pgvector、LangGraph。学概念，不把两套 API 名称强行对号入座。
6. 目前默认 Embedding 为离线 hashing 基线，reranker 默认关闭；配置了语义服务适配器不代表已完成真实语义模型评测。离线 Gold Replay 也不是模型真实准确率。
7. GraphRAG 为有边界的局部子图检索增强，不是复现全套社区检测/全局摘要算法。MCP 用官方 SDK 的无状态 JSON Streamable HTTP，只读工具不等于无需鉴权。
8. 项目没有自定义 `@Aspect` 审计切面；审计通过普通 Service 显式调用。AOP 课程主要帮助理解事务等代理行为。

<a id="l01"></a>

## L01 · Java / Spring：先读懂“对象是怎么接起来的”

**课程**：SSM P3–7、P21–27；Boot P3–6。若完全不懂构造器，再看 SSM P9、P13–15。无需从头刷完 P8–20 的旧 XML 写法。

**代码顺序**：

1. [PlatformApiApplication.java](../../platform-api/src/main/java/com/example/copilot/PlatformApiApplication.java)：应用启动与扫描边界。
2. [AnalysisJobController.java](../../platform-api/src/main/java/com/example/copilot/controller/AnalysisJobController.java) → [AnalysisJobService.java](../../platform-api/src/main/java/com/example/copilot/service/AnalysisJobService.java)：构造器注入和职责分层。
3. [AnalysisExecutionConfiguration.java](../../platform-api/src/main/java/com/example/copilot/config/AnalysisExecutionConfiguration.java)：配置类提供线程池等依赖。

**必须理解**：Java 类/接口/实现、泛型与集合、record、异常、构造器；`@Component/@Service/@Bean`、依赖方向、单例不等于线程安全。源码级 Bean 生命周期可以暂查文档。

**练习与验收**：不看 AI 解释，画出 Controller 的直接依赖；解释“为什么不在 Controller 里 new Service”。写一个小型接口与 Fake 实现的测试。讲清楚 Spring 管的对象与普通 DTO 的区别。

<a id="l02"></a>

## L02 · Boot 配置 / Web / 异常：追一条 HTTP 请求

**课程**：Boot P7–15；SSM P44–56、P62–65。SSM P90–104 与 Boot 课重复，作为查漏，不要求两套全看。

**代码顺序**：[application.yml](../../platform-api/src/main/resources/application.yml) → [AgentIntegrationProperties.java](../../platform-api/src/main/java/com/example/copilot/config/properties/AgentIntegrationProperties.java) → [AnalysisJobController.java](../../platform-api/src/main/java/com/example/copilot/controller/AnalysisJobController.java) → [CreateAnalysisJobRequest.java](../../platform-api/src/main/java/com/example/copilot/dto/request/CreateAnalysisJobRequest.java) → [GlobalExceptionHandler.java](../../platform-api/src/main/java/com/example/copilot/exception/GlobalExceptionHandler.java)。

**必须理解**：配置绑定与覆盖；HTTP 方法/状态码、JSON、Validation、DTO vs entity、ControllerAdvice。创建任务的 202 不是执行成功。

**练习**：在练习分支补“空问题/超长问题”的请求测试；用浏览器网络面板找到错误响应，再定位后端处理分支。

**验收**：能解释配置从哪里来、错误为何是 400/401/403/404；能独立为新增字段加校验、契约和测试。高级自定义 Starter 暂缓，按需看 Boot P19–24 理解自动配置。

<a id="l03"></a>

## L03 · MyBatis 与任务筛选：岗位硬要求优先

**课程**：SSM P28–29、P103；Boot P17。视频不是完整 MyBatis SQL 映射教程，补 [MyBatis XML 官方文档](https://mybatis.org/mybatis-3/sqlmap-xml.html)。选修 MP：SSM P105–114、P116–117，先在隔离小练习中使用，勿直接替换全部 JPA。

**代码顺序**：

1. [AnalysisJobSearchController.java](../../platform-api/src/main/java/com/example/copilot/controller/AnalysisJobSearchController.java) / [AnalysisJobSearchRequest.java](../../platform-api/src/main/java/com/example/copilot/dto/request/AnalysisJobSearchRequest.java)。
2. [AnalysisJobQueryService.java](../../platform-api/src/main/java/com/example/copilot/service/AnalysisJobQueryService.java)：身份范围、校验和只读事务。
3. [AnalysisJobQueryMapper.java](../../platform-api/src/main/java/com/example/copilot/mapper/AnalysisJobQueryMapper.java) ↔ [AnalysisJobQueryMapper.xml](../../platform-api/src/main/resources/mapper/AnalysisJobQueryMapper.xml)；再对照 [AnalysisJobSearchMapper.xml](../../platform-api/src/main/resources/mapper/AnalysisJobSearchMapper.xml)。
4. [UuidTypeHandler.java](../../platform-api/src/main/java/com/example/copilot/mybatis/typehandler/UuidTypeHandler.java) 与 [AnalysisJobQueryMapperIntegrationTest.java](../../platform-api/src/test/java/com/example/copilot/integration/AnalysisJobQueryMapperIntegrationTest.java)。

**必须理解**：namespace/方法对应、`#{...}` 参数绑定、动态条件、resultMap、count/page、稳定排序、UUID 映射；为什么租户/owner 来自认证身份而不是请求体。

**练习**：新增一个受限筛选条件，先写“本租户正确命中、其他租户不可见、非法参数拒绝”测试，再加 DTO → Service → Mapper → XML。不要用字符串拼接用户 SQL。

**验收**：能手写等价参数化 SQL；解释当前 JPA 与 MyBatis 各自负责什么，能回答为什么排序字段不能随意用 `${input}`。

<a id="l04"></a>

## L04 · SQL / PostgreSQL / 索引：不是看完 MySQL 安装课就够了

**课程**：SSM P40–42 只补事务。**现有五门课不覆盖完整 SQL 和调优**。SQL 基础薄弱时需补专项；若已能完成以下练习，不必再从头学完整 MySQL 管理课。

**学习顺序**：SELECT/NULL/WHERE → JOIN 与一对多去重 → GROUP BY/HAVING → 子查询/CTE → 窗口函数与环比 → 主外键/事务 → 索引与 EXPLAIN。MySQL 可学通用 SQL/B+Tree/事务概念；本项目重点是 PostgreSQL 方言、JSONB/UUID/FTS/pgvector，不能照搬 MySQL 执行计划和索引结论。

**代码**：[业务表结构](../../infra/docker/business-db/init/010-northwind-schema.sql)、[gold SQL](../../evaluation/northwind/nl2sql-gold-v2.jsonl)、[V7 索引](../../platform-api/src/main/resources/db/migration/V7__job_search_indexes.sql)、[query_plans.py](../../agent-service/app/evaluation/query_plans.py)、[查询计划报告](../../evaluation/northwind/week3-query-plans.json)。

**补学**：[PostgreSQL CTE](https://www.postgresql.org/docs/17/queries-with.html)、[EXPLAIN](https://www.postgresql.org/docs/17/using-explain.html)。

**练习**：手写季度销售额和环比；比较租户+时间筛选的执行计划，解释索引列顺序。小表选 Seq Scan 未必是缺陷；看估计/实际行数、扫描方式和成本，不靠“出现 Index Scan”单独验收。

**验收**：能说明为什么 COUNT 与分页放在一致性事务里；解释 OFFSET 与数据量、统计信息的关系。仅在练习数据上用 EXPLAIN ANALYZE，它会真正执行语句。

<a id="l05"></a>

## L05 · 身份 / 数据权限 / 审计

**课程**：SSM P31–42、P71–74（代理/事务/拦截概念）；补 [Spring Security JWT](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html)。此链接用于理解资源服务验证链，本项目有自己的登录签发和身份映射，不是照抄外部 issuer 示例。

**代码**：[SecurityConfiguration.java](../../platform-api/src/main/java/com/example/copilot/config/SecurityConfiguration.java) → [AuthenticationService.java](../../platform-api/src/main/java/com/example/copilot/service/AuthenticationService.java) → [CallerIdentity.java](../../platform-api/src/main/java/com/example/copilot/security/CallerIdentity.java) / [InternalServiceAuthenticator.java](../../platform-api/src/main/java/com/example/copilot/security/InternalServiceAuthenticator.java) → [AuditService.java](../../platform-api/src/main/java/com/example/copilot/service/AuditService.java) → [IntelligenceController.java](../../platform-api/src/main/java/com/example/copilot/controller/IntelligenceController.java)。

**必须理解**：认证 vs 授权、JWT 不能只解码不验签、租户过滤、角色约束、服务令牌与浏览器令牌的区别、可信头只能在服务边界内使用；事务代理与同类自调用限制。

**练习/验收**：复述 analyst/admin 的能力差异；给一个智能接口补跨租户、低权限和伪造身份测试。运行 `PlatformSecurityIntegrationTest` 与 `IntelligenceApiIntegrationTest`。说明哪些字段不应该进入日志或发往外部模型。

<a id="l06"></a>

## L06 · Redis / 后台任务 / SSE：读懂“请求已经返回，谁还在干活”

**课程**：Redis P7–10、P15、P18–21；LangGraph P107–113 只帮助理解流式事件。Redis P11–14、P22 作为数据结构扩展，不是 Streams 教程。

**代码**：[AnalysisJobDispatcher.java](../../platform-api/src/main/java/com/example/copilot/task/AnalysisJobDispatcher.java) → [JobDispatchLease.java](../../platform-api/src/main/java/com/example/copilot/task/JobDispatchLease.java) → [AnalysisJobWorker.java](../../platform-api/src/main/java/com/example/copilot/task/AnalysisJobWorker.java) → [RedisAnalysisEventStore.java](../../platform-api/src/main/java/com/example/copilot/repository/RedisAnalysisEventStore.java) → [AnalysisEventStreamService.java](../../platform-api/src/main/java/com/example/copilot/service/AnalysisEventStreamService.java) → [sse.ts](../../web/src/lib/sse.ts)。

**补学**：[Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/)、[Lua 原子执行](https://redis.io/docs/latest/develop/programmability/eval-intro/)。重点读 XADD/XRANGE、事件 ID、INCR/EXPIRE、SET NX EX 和 compare-and-delete；Lua 应短小，原子执行不代表免费或无限并行。

**必须理解**：事务提交后调度、线程池、租约 owner/TTL、事件顺序/断线重放、Redis 临时进度 vs PostgreSQL 最终状态。租约不是万能分布式锁，也不能单独保证 exactly-once。

**练习/验收**：解释同一幂等键重复请求、Redis 不可用、SSE 断线后的路径；运行 `make verify-p8`，从测试读懂 Last-Event-ID 和快照兜底。不要把 Pub/Sub、List、Streams 当成同一种东西。

<a id="l07"></a>

## L07 · 模型调用 / Prompt / 结构化输出

**课程**：RAG P4、P8–16、P22–26、P34–35；LangGraph P14–15。理解 Python 类型标注、Protocol、async/await、上下文管理器后再读适配器。

**代码**：[llm/provider.py](../../agent-service/app/llm/provider.py) → [llm/openai_compatible.py](../../agent-service/app/llm/openai_compatible.py) → [llm/models.py](../../agent-service/app/llm/models.py) → [llm/structured.py](../../agent-service/app/llm/structured.py) → [llm/fake.py](../../agent-service/app/llm/fake.py)。

**必须理解**：模型服务 HTTP 协议、Schema 验证、超时/状态码分类、有界重试、usage、脱敏；Prompt 不能代替输出校验。LangChain 的 JsonOutputParser 与这里的 Pydantic 校验概念相近，但调用代码不同。

**练习/验收**：用 Fake 返回非法 JSON 一次，再返回有效结构；解释为何 401 不该反复重试，429/超时怎样退避；运行 `make verify-p4`。真实 API 联调需你明确配置和执行；学习不依赖付费调用。

**补学**：[FastAPI](https://fastapi.tiangolo.com/tutorial/)、[Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/)。

<a id="l08"></a>

## L08 · RAG：文档如何变成可引用知识

**课程**：RAG P19–21、P26、P39–45、P48–52；基础薄弱再看 P46–54 项目整体，不需要照搬上传 UI。

**代码顺序**：[retrieval/parsing.py](../../agent-service/app/retrieval/parsing.py) → [retrieval/models.py](../../agent-service/app/retrieval/models.py) → [retrieval/embeddings.py](../../agent-service/app/retrieval/embeddings.py) → [retrieval/repository.py](../../agent-service/app/retrieval/repository.py) → [retrieval/service.py](../../agent-service/app/retrieval/service.py) → [retrieval/cache.py](../../agent-service/app/retrieval/cache.py)。

**必须理解**：chunk/overlap、页码/行号、向量维度与余弦相似、关键词召回、top-k、引用、tenant filter、文档版本与缓存键；Embedding 不等于生成模型。

**练习**：用现有指标 Markdown 追一条 chunk 的来源；更新文档，观察版本变化并证明旧引用/缓存失效；为无关问题补拒答测试。

**验收**：从“文件 → chunk → FTS/向量 → 融合 → 引用”讲完一遍；运行 `test_retrieval.py`，具备本地数据库后运行 `make verify-p6`。说明 hashing 基线为什么不能代表真实语义效果。

<a id="l09"></a>

## L09 · 混合检索 / Rerank / 评测

**课程**：RAG P20–21、P43–44、P52、P63–64 作为概念复习，不足以覆盖本单元实现。

**代码**：[retrieval/providers.py](../../agent-service/app/retrieval/providers.py)、[retrieval/repository.py](../../agent-service/app/retrieval/repository.py)、[V8 profile](../../platform-api/src/main/resources/db/migration/V8__embedding_profiles.sql)、[retrieval/evaluation.py](../../agent-service/app/retrieval/evaluation.py)、[retrieval/benchmark.py](../../agent-service/app/retrieval/benchmark.py)、[test_upgrade_retrieval.py](../../agent-service/tests/test_upgrade_retrieval.py)。

**补学**：[pgvector 官方说明](https://github.com/pgvector/pgvector)：距离算子、维度、HNSW/IVFFlat、过滤与召回权衡。先确认代码实际建了什么索引，不要把“知道 HNSW”说成“当前已经调优”。

**练习**：比较 lexical/vector/hybrid/hybrid_rerank；手算一例 RRF；给多相关文档题手算 Recall@K 与 MRR。换模型/profile/维度时检查为何要求重建索引数据，不能只改环境变量混用旧向量。

**验收**：用 `make upgrade-rag-eval` 看离线报告，指出哪些模式依赖真实服务、哪些结果只是基线；说出召回失败、重排失败、引用失败分别怎么查。真实语义对比尚需显式配置服务和真实评测，不从现有离线分数推断。

<a id="l10"></a>

## L10 · NL2SQL / SQL 安全：不要让模型拥有最终执行权

**课程**：RAG P12–16、P19、P58、P65。这里只是结构化生成/工具概念，不能替代 SQL 安全专项。

**代码顺序**：[metadata/introspection.py](../../agent-service/app/metadata/introspection.py) → [nl2sql/prompts.py](../../agent-service/app/nl2sql/prompts.py) → [nl2sql/service.py](../../agent-service/app/nl2sql/service.py) → [query_safety/guard.py](../../agent-service/app/query_safety/guard.py) → [query_safety/cost.py](../../agent-service/app/query_safety/cost.py) → [query_safety/executor.py](../../agent-service/app/query_safety/executor.py) → [query_safety/audit.py](../../agent-service/app/query_safety/audit.py)。

**必须理解**：schema allowlist、AST 与字符串检查的差异、只读角色/事务、超时/行列字节上限、成本阈值、修复次数上限、稳定错误码。用户意图检查与生成 SQL 检查是两层。

**练习/验收**：构造写语句、多语句、越权表和伪装 CTE，证明执行器调用次数为零；讲清“高成本待审批”与“危险 SQL 永久阻断”的差别。运行 `test_nl2sql.py`、`test_query_safety.py`，有库后运行 `make verify-safety`、`make verify-p5`。

<a id="l11"></a>

## L11 · LangGraph：状态、条件边与有界循环

**课程**：LangGraph P8–20、P27–28、P32–34、P40–47、P128–132。先学基本图，不用先学完全部并行归约与子图。

**代码顺序**：[agent/state.py](../../agent-service/app/agent/state.py) → [agent/models.py](../../agent-service/app/agent/models.py) → [agent/graph.py](../../agent-service/app/agent/graph.py) → [agent/actions.py](../../agent-service/app/agent/actions.py) → [agent/service.py](../../agent-service/app/agent/service.py)。

**必须理解**：state 的字段由哪个节点写、输入/输出、条件路由、生成→验证→修复的回边、最大次数、终止状态、动作协议与业务状态机之间的关系。图的可视化不是执行正确性的证据。

**练习/验收**：不看图，手动走一遍成功、修复成功、修复耗尽、策略拒绝四条路径；写一个 Fake action 覆盖失败分支，运行 `test_agent_workflow.py`。

<a id="l12"></a>

## L12 · Checkpoint / 人工审批 / 恢复 / 重试

**课程**：LangGraph P48–51、P56–60、P65–74、P84–86、P88–91。PostgreSQL 安装已会则跳 P61–64；长期记忆 P78–83 后置，不与 checkpoint 混淆。

**代码顺序**：[agent/checkpoint.py](../../agent-service/app/agent/checkpoint.py) → [agent/error_policy.py](../../agent-service/app/agent/error_policy.py) → [agent/steps.py](../../agent-service/app/agent/steps.py) → [ApprovalService.java](../../platform-api/src/main/java/com/example/copilot/service/ApprovalService.java) → [InternalAgentCallbackController.java](../../platform-api/src/main/java/com/example/copilot/controller/InternalAgentCallbackController.java) → [agent/demo.py](../../agent-service/app/agent/demo.py)。

**必须理解**：thread_id、checkpoint、interrupt、相同线程恢复、审批只决定一次、重启恢复、暂时性错误 vs 永久性错误、重跑节点与外部副作用的幂等问题。

**练习/验收**：`make upgrade-agent-demo` 跑离线修复→审批→恢复示例；解释重复审批和拒绝审批为何不执行 SQL；运行 `test_upgrade_contract.py` 与 `test_agent_workflow.py`，有库后运行 `make verify-p7`。不能把内存测试通过冒充数据库恢复验证。

<a id="l13"></a>

## L13 · 图谱 / Neo4j / 局部 GraphRAG

**课程**：RAG P14–15（结构化抽取）、P19（检索增强）；LangGraph P15（数据模型）。**五门课没有本单元的完整实现课**。

**补学**：[Neo4j Python 查询](https://neo4j.com/docs/python-manual/current/query-simple/)，重点是参数化 Cypher、MERGE/匹配/有界路径、事务和租户隔离；再按代码理解局部 GraphRAG。

**代码顺序**：[knowledge_graph/models.py](../../agent-service/app/knowledge_graph/models.py) → [knowledge_graph/service.py](../../agent-service/app/knowledge_graph/service.py) → [knowledge_graph/repository.py](../../agent-service/app/knowledge_graph/repository.py) → [knowledge_graph/metadata.py](../../agent-service/app/knowledge_graph/metadata.py) → [knowledge_graph/api.py](../../agent-service/app/knowledge_graph/api.py)。

**练习**：从一小段指标文档抽实体/关系/原文 quote；伪造一句不在原文的 quote，证明不会持久化。比较普通 RAG 与子图增强给出的证据，而不是只比回答长度。

**验收**：运行 `test_knowledge_graph.py` 与 `make upgrade-extraction-eval`；真实 Neo4j 集成按交付手册运行 `test_graph_integration.py`。解释两租户同名实体为何不应连成一张图，说明这是局部检索而非全局社区摘要算法。

<a id="l14"></a>

## L14 · MCP：协议不是“写五个函数”

**课程**：RAG P55–58、P65；LangGraph P41、P101–105 是工具调用基础。MCP 协议与 HTTP 传输需要另学。

**补学**：[官方 Python SDK](https://github.com/modelcontextprotocol/python-sdk)；项目锁定 SDK 1.x，请选对应版本说明，不机械复制主分支将来的接口。

**代码顺序**：[mcp_server.py](../../agent-service/app/mcp_server.py) → [IntelligenceController.java](../../platform-api/src/main/java/com/example/copilot/controller/IntelligenceController.java) → [openapi-intelligence.yaml](../../contracts/openapi-intelligence.yaml) → [test_mcp_protocol.py](../../agent-service/tests/test_mcp_protocol.py)。

**必须理解**：initialize、tools/list、tools/call、Schema、readOnlyHint 只是声明、Streamable HTTP、鉴权与租户上下文。项目不允许浏览器自填服务身份绕过 Java。

**练习/验收**：运行 `test_mcp_protocol.py`；解释一个 tool 从协议请求到检索结果的链路；伪造 tenant/缺少令牌时拒绝；列清五个工具实际能力，不把协议包装说成新的 Agent。

<a id="l15"></a>

## L15 · React / Next.js / ECharts / 联调

**课程**：SSM P57–58、P66–70、RAG P47/P54/P67 仅作联调/界面思路参考。**项目不是课程中的传统页面或 Streamlit**。

**补学**：[React Learn](https://react.dev/learn)、[Next.js App Router](https://nextjs.org/docs/app)、[ECharts graph 配置](https://echarts.apache.org/en/option.html#series-graph)。先掌握 TypeScript 对象/联合类型、async/await、React state/effect，再读大组件。

**代码顺序**：[types.ts](../../web/src/lib/types.ts) → [api.ts](../../web/src/lib/api.ts) → [Web 同源代理](../../web/src/app/api/platform/%5B...path%5D/route.ts) → [CopilotApp.tsx](../../web/src/components/CopilotApp.tsx) → [sse.ts](../../web/src/lib/sse.ts) → [KnowledgeGraphView.tsx](../../web/src/components/KnowledgeGraphView.tsx) / [graph.ts](../../web/src/lib/graph.ts)。

**练习**：在网络面板追一条失败请求，区分 Web 代理/Java/Python 谁返回；加一个“空图谱”状态测试，补图节点/边转换边界测试；不执行模型生成脚本。

**验收**：运行 `make verify-p9`（会包含后端检查，需 Docker）或先仅运行 Web 的 test/lint/typecheck；解释为什么浏览器不直连 Python、图表采用受限规范而非任意 JavaScript。

<a id="l16"></a>

## L16 · 验证 / 观测 / 部署 / 作品集

**课程**：Boot P15、P31、P34；SSM P102；LangGraph P48–51 用来理解故障测试。Boot P32 的“开放全部端点”不要照搬；P33 Admin 与项目 Prometheus 不是一回事。

**代码顺序**：[Makefile](../../Makefile) → [CI](../../.github/workflows/ci.yml) → [docker-compose.full.yml](../../docker-compose.full.yml) → [observability.py](../../agent-service/app/observability.py) / [TraceIdFilter.java](../../platform-api/src/main/java/com/example/copilot/common/TraceIdFilter.java) → [evaluation/runner.py](../../agent-service/app/evaluation/runner.py) → [portfolio 验证脚本](../../scripts/verify-portfolio-evidence.py)。

**补学**：[Docker Compose](https://docs.docker.com/compose/)、[Testcontainers Java](https://java.testcontainers.org/)、[pytest](https://docs.pytest.org/en/stable/)、[Git 基础](https://git-scm.com/book/zh/v2)。Linux 至少会进程/端口/环境变量/日志/文件权限；不需要先学 Kubernetes。

**练习/验收**：亲自复现一个超时或依赖不可用问题，按 trace 查到失败边界；跑一个单元测试和一个真实依赖集成测试，讲清差别；能用 git diff 评审、提交和回滚自己的一次小改动。真实模型效果、公网部署、录屏没有证据就不写“已完成”。

## 建议学习节奏（不是新的强制排期）

以每天约 2–3 小时为例；如果前置薄弱，延长相应单元，不用赶日历：

| 阶段 | 单元 | 产物 |
|---|---|---|
| 第 1–2 周 | L01–L03 | 一张请求链路图、一条独立完成的筛选/校验改动及测试 |
| 第 3 周 | L04–L06 | 一份 SQL/索引解释、权限拒绝与 SSE 重连演示 |
| 第 4–5 周 | L07–L10 | 文档入库→引用链路说明、RAG 小评测、危险 SQL 零执行证据 |
| 第 6 周 | L11–L12 | 状态流转图、修复上限和审批重启恢复演示 |
| 第 7 周 | L13–L15 | 带原文证据的关系抽取、MCP 调用与图谱页面联调 |
| 第 8 周 | L16 + 总复习 | 故障定位记录、部署说明、5–7 分钟完整演示 |

与原“改造第 3～10 周”对照：查询/索引 → L03–L04；RAG → L07–L09；Agent → L11–L12；抽取/Neo4j/GraphRAG → L13；MCP → L14；关系网络/验收 → L15–L16。这里是**理解代码的依赖顺序**，不是要求按历史提交顺序死记。

## 每次学习的固定闭环

1. 看 1–3 个相关分集，写 5 句话说明输入、输出和限制。
2. 打开索引里的生产文件和对应测试，逐行走一个具体样例。
3. 先预测某个边界输入的结果，再运行测试验证。
4. 在练习分支只改一个小点，自己先写方案或测试；让 Codex 做解释、提示和评审。
5. 记录“我能解释 / 仍需提示 / 尚未验证”。连续两次能独立完成，才把该单元标记掌握。

可直接这样提问（不是本仓库自动执行的指令）：

> 今天学 L03。请先只读 AnalysisJobQueryService、Mapper 和 XML，用一个具体请求解释参数怎样变成 SQL。区分课程已有知识和需要补的知识，先不要修改代码。给我 3 道预测结果题，等我回答后再评价。之后让我先写一个筛选条件的测试，你只指出问题，最后再给最小修订建议。

> 我准备改 L08 的文档版本失效。请先让我复述调用链，检查遗漏，再协助我拆成一个可测试的小步骤。不要一次生成整个功能；明确哪些代码我必须能逐行解释，哪些库内部实现只需掌握契约。

## 最终自检

- 不看说明，能从登录讲到分析结果、租户权限、模型调用、SQL 安全、审批、SSE、图谱和 MCP。
- 能独立完成一个小需求，从接口/数据库到页面和测试，而不只是修改 Prompt。
- 能指出当前默认离线模式、未完成的真实评测和部署限制。
- 能用实际测试/报告支持简历中的每个数字；理解失败案例比背“项目用了什么框架”更重要。

