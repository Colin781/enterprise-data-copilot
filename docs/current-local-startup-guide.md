# Enterprise Data Copilot 当前本地启动手册

本文记录 P0～P12 完成后的实际启动流程。新使用者优先用完整 Compose 栈；需要热重载时再使用三个开发终端。两种模式不能同时占用相同宿主机端口。除明确说明外，命令均从项目根目录执行：

```text
/Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
```

## 1. 运行组成

完整系统包含 7 个服务：

| 组件 | 运行方式 | 默认地址或端口 | 职责 |
|---|---|---:|---|
| Web | Next.js | `http://localhost:3000` | 登录、指标文档、分析、图表、轨迹和审批界面 |
| Platform API | Spring Boot | `http://localhost:8080` | 身份、租户、任务、审批、异步调度和结果持久化 |
| Agent Service | FastAPI | `http://localhost:8000` | RAG、选表、NL2SQL、安全校验、执行和结果组合 |
| Platform PostgreSQL | Docker Compose | `localhost:5432` | 平台数据和 LangGraph checkpoint |
| Business PostgreSQL | Docker Compose | `localhost:5433` | 只读 Northwind 业务数据 |
| Redis | Docker Compose | `localhost:6379` | 异步任务的短期进度和 SSE 重放 |
| Prometheus | 完整 Compose 模式 | `http://localhost:9090` | 抓取 Platform 与 Agent 指标 |

调用方向如下：

```text
浏览器 -> Web :3000 -> Platform API :8080 -> Agent Service :8000
                              |                    |
                              v                    v
                     Platform PostgreSQL    Business PostgreSQL
                              |
                              v
                            Redis

Agent Service -> 配置的模型服务（仅真实模型问题）
Prometheus :9090 -> Platform API / Agent Service（抓取指标）
```

浏览器不会直接获得 Agent 地址、数据库密码或服务间令牌。

## 2. 前置条件

完整 Compose 启动时，本机只需要 Docker Desktop／Docker Engine（含 Compose）。若要使用开发热重载或在宿主机跑验收，还需要：

- Java 21；仓库自带 Maven Wrapper，不要求全局安装 Maven。
- Python 3.12 和 `uv`。
- Node.js 22 或更高版本。
- 仅开发热重载模式需要 pnpm 11；如果依赖已经安装，可以直接使用仓库内的 Next.js 二进制。
- 可用的 OpenRouter API Key；只有真实模型端到端运行需要它。

检查版本：

```bash
java -version
python3 --version
uv --version
node --version
docker --version
docker compose version
```

开发热重载模式另外检查 `pnpm --version`。完整 Compose 模式会在镜像内安装锁定依赖，不依赖宿主机 pnpm、uv 或 Java；这些工具只在本机运行开发服务或验收命令时需要。

首次安装 Maven、Python、Node 依赖或拉取 Docker 镜像时需要网络。离线环境只能复用已经存在的 `.venv`、`node_modules`、Maven 缓存和 Docker 镜像。

## 3. 创建和填写 `.env`

进入仓库：

```bash
cd /Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
```

仅在 `.env` 不存在时，从模板创建：

```bash
make env
```

`make env` 不会覆盖已有 `.env`。如果模板增加了字段，需要人工对照 `.env.example` 补齐。

### 3.1 生成本地随机值

分别生成 JWT secret 和服务间 token：

```bash
openssl rand -hex 32
openssl rand -hex 32
```

把第一条结果填入：

```dotenv
PLATFORM_JWT_SECRET=<第一条随机字符串>
```

把第二条结果同时填入下面两个配置。两个值必须逐字符完全一致：

```dotenv
AGENT_SERVICE_TOKEN=<第二条随机字符串>
AGENT_WORKFLOW_SERVICE_TOKEN=<第二条随机字符串>
```

这两个 token 不是从网站领取的。它们是本地 Java Platform 和 Python Agent 之间共享的内部凭据，由项目运行者自己生成。

### 3.2 配置 OpenRouter

在 `.env` 中填写：

```dotenv
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=<你的 OpenRouter API Key>
LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
LLM_STRUCTURED_OUTPUT_MODE=json_schema
```

只有提交真实模型分析问题时才需要有效的 Key。健康检查、危险问题拒绝、离线评测和无模型费用压测不调用 OpenRouter。模型源可通过 `LLM_PROVIDER`、`LLM_BASE_URL` 和 `LLM_MODEL` 配置；切换供应商前要确认结构化输出兼容性，不要把失败归因于模型源而未经验证就更换。

不要把真实 API Key 写入 `.env.example`、Git 提交、截图或日志。

### 3.3 保持固定约束值

以下值是当前实现的固定边界，不要随意修改：

```dotenv
NL2SQL_MAX_REPAIRS=2
AGENT_WORKFLOW_MAX_REPAIRS=2
RAG_EMBEDDING_DIMENSIONS=64
BUSINESS_DB_ALLOWED_SCHEMA=northwind
LANGGRAPH_STRICT_MSGPACK=true
```

当前代码把环境变量解析为受范围约束的整数，而不是 `Literal`，因此 `.env` 中的字符串形式 `2` 和 `64` 可以正常通过 Pydantic Settings 校验。

### 3.4 不要直接 `source .env`

模板中有包含空格的值，例如 `Northwind Demo` 和 `Enterprise Data Copilot`。不要执行：

```bash
source .env
```

否则 shell 会把空格后的内容当成命令。项目的 Makefile 会读取并导出 `.env`，正常启动请使用 `make` 命令。

完整 Compose 模式中，容器间地址由 `docker-compose.full.yml` 设置，不要把 `.env` 里的 `localhost` 手工改成容器名。Compose 用 `AGENT_SERVICE_TOKEN` 给 Java 与 Python 注入同一个服务令牌；本机开发模式仍要求 `AGENT_WORKFLOW_SERVICE_TOKEN` 与它相同。更改 `PLATFORM_BOOTSTRAP_PASSWORD` 不会覆盖已有数据库用户的密码；已有数据卷请继续使用原密码或通过正式用户管理流程变更。

## 4. 首选启动方式：完整 Compose 栈

确保 Docker 已启动，完成第 3 节的 `.env` 配置后，从仓库根目录执行：

```bash
make stack-config
make stack-up
```

`make stack-up` 会构建三个应用镜像，启动 Web、Platform API、Agent、两套 PostgreSQL、Redis 和 Prometheus，等待配置了健康检查的服务就绪，并幂等加载固定 Northwind 数据。第一次拉镜像和安装镜像内依赖需要网络；不需要先运行 `make setup`，也不要再同时启动 `make dev`。

```bash
docker compose -f docker-compose.yml -f docker-compose.full.yml ps
curl -fsS http://localhost:3000/health
curl -fsS http://localhost:8080/actuator/health
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:9090/-/ready
```

预期四个 HTTP 检查成功。打开 `http://localhost:3000` 使用第 10 节的账号登录；Prometheus 位于 `http://localhost:9090`，其 Targets 页面应显示 `platform-api` 和 `agent-service` 为 `UP`。Prometheus 容器没有单独的 Compose healthcheck，以 `/-/ready` 和 Targets 为准。

仅查看当前栈日志时可用：

```bash
docker compose -f docker-compose.yml -f docker-compose.full.yml logs --tail=100 agent-service platform-api web prometheus
```

停止完整栈但保留数据库卷：

```bash
make stack-down
```

`stack-down` 会停止两套数据库和 Redis；下一次运行 `make stack-up` 会复用保留的数据卷。若只是想使用开发热重载，先停止完整栈，再从第 5 节开始。

## 5. 开发热重载模式：第一次安装依赖

```bash
make setup
```

它会执行：

```text
agent-service: uv sync --all-groups
web:           pnpm install --frozen-lockfile
```

如果当前是离线环境，并且 `.venv` 与 `web/node_modules` 已经存在，可以跳过 `make setup`。

如果 pnpm 因 Corepack 或包管理器签名校验无法启动，但 `web/node_modules` 已完整安装，这不是项目构建错误。启动 Web 时可直接使用锁定的本地 Next.js 二进制：

```bash
make PNPM=./node_modules/.bin/next dev-web
```

等价的本地验证命令为：

```bash
cd web
node --experimental-strip-types --test tests/*.test.ts
./node_modules/.bin/eslint .
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/next build
```

## 6. 启动数据库与 Redis

确保 Docker Desktop 已经启动，然后执行：

```bash
make compose-up
```

该命令会：

1. 启动 Platform PostgreSQL、Business PostgreSQL 和 Redis。
2. 等待容器健康检查通过。
3. 幂等加载 `northwind-compact-v1` 固定数据。
4. 幂等补齐 `northwind_reader` 只读账号及权限。

检查容器：

```bash
docker compose ps
```

如需单独重载固定数据：

```bash
make load-northwind
```

该操作不会删除数据卷，只会按固定主键恢复仓库定义的数据。

## 7. 三个终端分别运行开发服务

分开启动便于判断错误来自哪一层。先完成第 5～6 节，不要与第 4 节的完整 Compose 栈同时运行。

### 终端一：Platform API

```bash
cd /Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
make dev-platform
```

成功标志包括：

```text
Tomcat started on port 8080
Started PlatformApiApplication
```

开发 bootstrap 会幂等创建：

- 租户：`northwind`
- 管理员：`admin@northwind.local`
- 分析员：`analyst@northwind.local`
- 初始密码：`change-me-demo`
- 数据源：`Northwind read-only`

### 终端二：Agent Service

```bash
cd /Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
make dev-agent
```

成功标志：

```text
Uvicorn running on http://127.0.0.1:8000
Application startup complete.
```

如果需要显式指定本机 `uv`：

```bash
make UV="$(command -v uv)" dev-agent
```

### 终端三：Web

正常情况：

```bash
cd /Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
make dev-web
```

如果 pnpm 在离线环境中因签名校验不能启动，但 `web/node_modules` 已存在：

```bash
cd /Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
make PNPM=./node_modules/.bin/next dev-web
```

成功标志：

```text
Local: http://localhost:3000
Ready
```

## 8. 可选：一条命令启动开发服务

配置与依赖已经确认无误后，可以运行：

```bash
make dev
```

它会先执行 `compose-up`，再并行启动三个应用服务。缺点是日志混在同一个终端中，首次排错不建议使用。

## 9. 健康检查

三个应用服务都启动后执行：

```bash
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:3000/health
```

预期三个响应的 `status` 都是 `UP`。

Spring Boot readiness 也可检查：

```bash
curl -fsS http://localhost:8080/actuator/health
```

如果端口被占用：

```bash
lsof -nP -iTCP:3000 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

先确认占用端口的是不是本项目旧进程，再决定是否停止；不要盲目杀进程。

## 10. 浏览器操作顺序

打开：

```text
http://localhost:3000
```

如果没有修改演示密码，使用管理员登录：

```text
租户：northwind
邮箱：admin@northwind.local
密码：change-me-demo
```

也可以用分析员账号；若在首次创建账号前改过 `.env` 的 `PLATFORM_BOOTSTRAP_PASSWORD`，请使用改后的密码：

```text
租户：northwind
邮箱：analyst@northwind.local
密码：change-me-demo
```

管理员可以上传指标文档和处理审批；分析员可以提交分析任务。

## 11. 上传指标知识文档

进入“指标知识库”，上传仓库中的：

```text
knowledge/northwind/retail-metrics-v1.md
```

推荐标题：

```text
retail-metrics-v1
```

成功后页面会显示文档版本和 `ACTIVE` 状态。更新同名标题会生成新版本并使旧版本失效。

如果上传返回 500，依次确认：

1. Agent 日志是否收到 `POST /internal/v1/knowledge/documents`。
2. 两个服务间 token 是否完全一致。
3. Platform 和 Agent 是否都在修改 `.env` 后重新启动。
4. Platform 是否正在运行当前已修复的 HTTP/1.1 与内部鉴权代码。

## 12. 提交可验证的问题

当前固定 Northwind 数据只覆盖 2024～2025 年。推荐使用：

```text
2025 年每季度销售额是多少？
```

已验证结果：

| quarter_start | total_sales |
|---|---:|
| 2025-01-01 | 4151.76000 |
| 2025-04-01 | 4103.62600 |

正常页面应显示：

- 任务状态 `COMPLETED`。
- `classify`、`retrieve_metrics`、`select_schema`、`generate_sql`、`guard_sql`、`execute_sql`、`verify`、`compose` 全部成功。
- 只读 SQL。
- 两行数据。
- `quarter_start` 为横轴、`total_sales` 为序列的折线图。

问题“1997 年每季度销售额是多少？”现在也会完成，但由于固定数据没有 1997 年记录，会返回 0 行。这是数据事实，不是服务失败。

## 13. 常用验收命令

基础检查：

```bash
make compose-config
make contract-test
make lint
make build
```

按阶段验收：

```bash
make verify-readonly
make verify-p2
make verify-safety
make verify-p4
make verify-p5
make verify-p6
make verify-p7
make verify-p8
make verify-p9
make verify-p10
make p10-eval
make verify-p11
make verify-p12
```

`make verify-all` 会运行 P1～P12 全部本地验收。

如果 `uv` 或 pnpm 在离线环境中无法启动，但依赖已安装，可分别使用：

```bash
cd agent-service
./.venv/bin/ruff format --check app tests
./.venv/bin/ruff check app tests
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/pytest -q -p no:cacheprovider
```

```bash
cd web
node --experimental-strip-types --test tests/*.test.ts
./node_modules/.bin/eslint .
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/next build
```

## 14. 停止服务

完整 Compose 模式运行 `make stack-down`；数据库卷默认保留。开发热重载模式在三个应用终端分别按 `Ctrl+C`。

如果还要停止数据库和 Redis：

```bash
make compose-down
```

`make compose-down` 也默认保留 Docker volumes。除非明确要清空全部本地数据，否则不要使用带 `-v` 的删除命令。

## 15. 最短启动清单

首次或演示推荐：

```bash
cd /Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
make env
# 按第 3 节填写 .env
make stack-config
make stack-up
```

访问 `http://localhost:3000`。若已安装开发依赖并希望热重载，先 `make stack-down`，再执行：

```bash
cd /Users/colin/Documents/ChatGPT/PyGPT/enterprise-data-copilot
make compose-up
```

然后打开三个终端依次运行：

```bash
make dev-platform
make dev-agent
make dev-web
```

最后检查：

```bash
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:3000/health
```

两种模式都通过 `http://localhost:3000` 登录，不要同时运行。
