# ADR-0003：指标知识采用 lexical + vector + RRF 混合检索

- 状态：Accepted
- 日期：2026-09-18
- 决策者：项目维护者

## 背景

指标定义既包含稳定业务术语，也包含自然语言同义表达。仅使用全文检索对精确术语可解释且可复现，但对改写问题召回不足；仅使用向量检索又可能把语义相近但口径不同的片段排在前面。

## 决策

- 保留 PostgreSQL lexical 检索作为可复现基线。
- 使用固定维度向量检索覆盖语义改写。
- 通过加权 Reciprocal Rank Fusion 合并排名，不直接混合不可比的原始分数。
- 返回文档版本、章节和定位信息，证据不足时拒答。
- 每次变更都用相同 24 条数据集比较 lexical、vector、hybrid 的 Recall@5、MRR、引用命中率和拒答准确率。

## 证据

当前离线报告中三种模式 Recall@5 均为 1.0；vector MRR 为 0.885，lexical 与 hybrid MRR 为 1.0。结果来自 `evaluation/northwind/p10-offline-baseline.json`，不代表外部语料或真实 embedding 模型的泛化能力。

## 后果

多维护一条检索路径和融合参数，但获得了可比较基线、确定性回归证据和更清晰的失败定位。生产替换 embedding provider 时仍必须保留 lexical 基线与相同评测集。
