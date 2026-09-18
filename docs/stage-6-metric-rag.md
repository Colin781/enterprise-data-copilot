# P6 指标知识库 RAG 验收记录

## 本阶段目标

为后续 Agent 流程提供可引用、可评测、按租户隔离的指标知识检索。P6 只负责文档解析、索引、检索和引用；将检索节点接入 LangGraph、审批恢复及端到端任务属于 P7。

## 已实现能力

1. **Markdown/PDF 摄取**：Markdown 保留标题和行号范围，PDF 保留页码；文件大小、PDF 页数、空文档、乱码与加密 PDF 均有明确限制或拒绝路径。
2. **稳定分块与来源定位**：按章节分块，长章节使用有界重叠；每块保存文档标题、版本、章节、来源定位和稳定 `section_key`。
3. **租户隔离与版本管理**：所有写入和检索显式携带 `tenant_id`。同标题文档更新会创建新版本、将旧版本标记为 `SUPERSEDED` 并删除旧 chunk/embedding。
4. **全文检索基线**：PostgreSQL 使用生成列 `tsvector`、GIN 索引、`websearch_to_tsquery` 和 `ts_rank_cd`。
5. **向量检索基线**：pgvector 使用 64 维确定性 hashing embedding 和 HNSW cosine 索引。Provider 是可替换协议，基线不联网、不消耗额度，也不把测试数字冒充真实 embedding 模型质量。
6. **混合检索**：使用加权 Reciprocal Rank Fusion；`k=60`，lexical/vector 权重为 `3:1`。较高的词法权重反映当前中文小语料与 hashing baseline 的实际对比结果。
7. **引用和拒答**：每个命中返回文档、版本、章节和行号/页码引用。没有超过证据阈值时返回 `should_answer=false`，供后续 Agent 明确拒答或澄清。
8. **缓存失效**：缓存键包含租户、查询、模式、Top-K 和语料版本；文档更新后立即失效当前租户缓存。

## 数据库迁移

Flyway V3 创建 `metric_documents` 与 `metric_chunks`，启用 pgvector，并建立：

- 当前有效文档的租户内唯一索引；
- 全文检索 GIN 索引；
- embedding cosine HNSW 索引；
- 租户、文档及版本相关约束。

Java Testcontainers 镜像同步改为 `pgvector/pgvector:pg17`，避免 V3 在不含 vector 扩展的普通 PostgreSQL 镜像上失败。

## 评测集与结果

`evaluation/northwind/rag-gold-v1.jsonl` 包含 24 条中文问题：20 条可回答指标定义题和 4 条知识库外拒答题。离线固定语料为 `knowledge/northwind/retail-metrics-v1.md`。

| 模式 | Recall@5 | MRR | 引用命中率 | 拒答正确率 |
|---|---:|---:|---:|---:|
| lexical | 100% | 100% | 100% | 100% |
| vector hashing baseline | 100% | 88.5% | 100% | 100% |
| weighted RRF hybrid | 100% | 100% | 100% | 100% |

这些数字证明当前固定语料上的检索、融合、引用和拒答流水线可重复运行；它们不代表真实企业语料或托管 embedding 模型上的生产效果。可追溯 JSON 位于 `evaluation/northwind/p6-rag-baseline.json`。

## 自动化证据

默认测试覆盖：

- Markdown 标题/行号和 PDF 页码解析；
- 文件与页数限制、空文档和无效编码；
- 分块边界、embedding 确定性与归一化；
- 租户隔离、引用字段、RRF 排序与证据不足拒答；
- 文档升级、旧 chunk/embedding 删除和缓存失效；
- 24 条题在 lexical/vector/hybrid 三种模式下的 Recall@5、MRR、引用命中率和拒答正确率。

真实 PostgreSQL 集成测试额外覆盖 `tsvector` 全文检索、pgvector cosine 检索、混合检索、租户隔离以及版本替换。运行：

```bash
make compose-up
make verify-p6
make rag-eval
```

2026-09-15 本地实测结果：

- `make verify-p6`：14 passed，其中 1 项直接连接真实 PostgreSQL + pgvector。
- Python 全量联合回归：105 passed；P2、安全纵切、P5、P6 的数据库测试全部启用，无跳过项。
- Java：14 passed；Testcontainers 使用 pgvector PostgreSQL 17，Flyway V1～V3 从空库执行成功，并验证 vector 扩展、知识表和 `vector(64)` 字段。
- Python Ruff、Java Spotless、Web ESLint/TypeScript、Web 生产构建和 Compose 配置均通过。

## 后续衔接状态

- P7 已完成 LangGraph 检索节点、PostgreSQL checkpointer、`agent_steps`、引用状态传递和审批恢复；
- Java 文档上传接口与 Python 索引服务的产品化接线随 P9 管理界面一起完成；
- 使用真实 embedding 模型的独立质量/成本对比留给 P10 完整评测。
