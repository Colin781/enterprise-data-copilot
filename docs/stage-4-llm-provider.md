# P4 模型适配与结构化输出验收记录

## 本阶段完成了什么

P4 按收敛版路线建立 Python Agent 的模型访问底座，但不生成 SQL，也不调用真实模型完成业务分析。

1. **统一 Provider 边界**：业务层只依赖 `LLMProvider` 协议和 `StructuredLLMClient`，不依赖 OpenRouter 或某个具体模型 SDK。
2. **OpenAI-compatible 适配器**：同一个实现支持 OpenRouter 和其他兼容 `/chat/completions` 的服务。
3. **严格结构化输出**：调用方必须提供 Pydantic 响应模型；适配器把 JSON Schema 发送给供应商，返回内容再次由 Pydantic 校验。
4. **Fake LLM**：测试使用脚本化响应，不访问网络、不消耗额度，并能准确检查重试次数和请求参数。
5. **有界重试**：超时、限流和临时不可用错误按指数退避重试，总尝试次数有上限；非法 JSON 或不符合 Schema 的响应最多重试一次。
6. **稳定错误分类**：区分配置、鉴权、请求拒绝、限流、超时、供应商不可用和非法结构化响应。
7. **资源限制**：请求具有连接超时、总体超时和最大输出 Token 限制，全部集中在 `LLM_*` 环境变量中。
8. **敏感信息保护**：API Key 使用 `SecretStr`；请求和响应正文不进入对象 repr、重试日志或公开异常；校验错误只保留字段位置与错误类型。

## 代码边界

| 文件 | 作用 |
|---|---|
| `app/llm/provider.py` | 定义供应商无关的异步协议 |
| `app/llm/openai_compatible.py` | 构造兼容请求并分类 HTTP/网络错误 |
| `app/llm/structured.py` | Pydantic 校验、一次非法输出重试和指数退避 |
| `app/llm/fake.py` | 为测试提供零费用、可重复的模型替身 |
| `app/llm/errors.py` | 定义稳定且不泄密的错误码 |
| `app/llm/models.py` | 定义消息、请求、Token 用量和结构化结果模型 |
| `app/llm/factory.py` | 从集中配置创建真实 Provider 与结构化客户端 |

## 配置方式

默认供应商是 OpenRouter。真实密钥只允许从环境变量或本地 `.env` 注入：

```dotenv
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=replace-with-your-provider-key
LLM_MODEL=openai/gpt-4.1-mini
```

模型名没有散落在业务代码中，因此在同一兼容供应商内切换模型只改 `LLM_MODEL`。自动化测试不读取也不需要真实密钥。

OpenRouter 模式要求非空 API Key；受信任的本地 OpenAI-compatible 服务可以不设置 Key，此时适配器不会发送空的 `Authorization` 请求头。

## 自动化验收证据

P4 专项测试覆盖：

- Fake Provider 符合统一协议并返回 Pydantic 对象。
- 请求携带 JSON Schema、严格模式和最大 Token 限制。
- 非法 JSON 第一次失败后重试，第二次仍失败则返回 `LLM_INVALID_RESPONSE`。
- Pydantic 字段错误保留安全的位置和类型，不回显原始内容。
- 超时重试遵循指数退避，耗尽后返回 `LLM_TIMEOUT`。
- 鉴权错误不重试；401、429、500、504 和网络超时被稳定分类。
- OpenRouter 缺少密钥时给出稳定配置错误；本地兼容服务可以显式使用无鉴权模式。
- 请求对象、Provider repr、异常和日志均不包含测试中的密钥、DSN、提示词或模型返回正文。
- `LLM_MODEL` 可以只通过环境变量切换。

最终本地结果：

- P4 专项测试 17 项全部通过，全程使用 Fake LLM 或内存 HTTP transport。
- Python 全量测试 36 项通过，5 项真实业务数据库测试按默认配置跳过。
- Python Ruff 检查与格式检查通过，`uv sync --locked --all-groups --offline` 通过。
- Java 13 项回归测试全部通过，其中 6 项使用 Testcontainers + PostgreSQL 17。
- Web ESLint、TypeScript 类型检查和 Docker Compose 配置检查均通过。

运行方式：

```bash
make verify-p4
```

## 明确留给后续阶段

- P4 不定义分析计划和 SQL 结构；它们属于 P5。
- P4 不连接业务数据库，也不绕过已有只读边界。
- P4 不实现 RAG、LangGraph、审批、异步任务或 SSE。
- 真实供应商 smoke test 需要用户自行提供 API Key，因此不作为无额度自动化验收条件。
