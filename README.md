# mini-harness

> 一个分阶段演进的迷你 LLM Agent 框架：工具运行时、上下文工程、状态持久化

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-v0.11.0-purple)
![Status](https://img.shields.io/badge/Status-Phase%2011%20%28Commercial%20Platform%29%20Done-brightgreen)

## 目录

- [简介](#简介)
- [已实现能力](#已实现能力phase-110)
- [路线图](#路线图)
- [快速开始](#快速开始)
- [运行流程](#运行流程)
- [项目结构](#项目结构)
- [设计要点](#设计要点)
- [开发状态](#开发状态)
- [贡献](#贡献)
- [更新日志](#更新日志)
- [许可证](#许可证)

## 简介

mini-harness 是一个分阶段演进的 LLM Agent 框架（Harness），目标是从内核出发，逐步补全一个生产级 Agent 系统所需的全部基础设施。项目按 11 个阶段推进，**Phase 1–11 全部完成（v0.11.0）**。

从 v0.10.0 起采用一条固定规则：**旧能力 + 新能力 = 新版本**，不再用「新增片段」覆盖「旧完整文件」而导致既有能力消失。本次同时对 Phase 1–9 教程基线做了 **Canonical Baseline Repair**，恢复此前被精简示例误删的能力（`ToolMiddleware`、`ContextPolicy` / `sources`、`Step` / `RuntimeEvent`、完整 SQLite Schema、完整 MCP 网关与降级逻辑、`OpenAIEmbeddingProvider` 等）。

已完成的 Phase 1–11 把「模型会调用工具」与「谁可以使用它」拆解成十个可独立演进的子系统：

- **工具运行时**：统一工具定义（JSON Schema）、Pydantic → Schema 工厂、JSON Schema 参数校验（拒绝外部 `$ref`）、权限检查、超时控制、重试策略、统一结果对象
- **上下文工程**：Token 预算与安全边距、分区组装指令（系统指令 + 工作状态 + 检索知识 + 外部上下文）、历史窗口与超预算裁剪（记录丢弃消息数）
- **状态与持久化**：Conversation / Run / Step / Checkpoint / RuntimeEvent 状态模型、SQLite 仓储（Repository）+ 工作单元（UnitOfWork）事务、多轮会话历史回放
- **检索增强（RAG）**：文档加载与字符切分（带重叠）、稳定 ID、向量化（Qwen / OpenAI 嵌入）、向量存储（Chroma）、稠密检索与可插拔重排、证据化结果投影
- **MCP 集成**：MCP Server 配置与网关（HTTP / STDIO 双传输）、工具发现与统一适配（权限 / 策略 / 元数据）、资源读取、可选服务器降级
- **可观测性**：OpenTelemetry 追踪（span）与指标（计数 / 直方图）、结构化 JSON 日志、模型用量与成本核算、Console / OTLP 双导出
- **评估（Evaluation）**：JSONL 评测数据集与格式校验、确定性评估器（答案包含 / 必需工具 / 禁止工具 / 最大步数）、可选 LLM Judge（参考答案 / 评分标准）、评测报告落盘与质量门、基线回归对比
- **安全（Security）**：输入 / 输出 Guard（长度、Prompt Injection 信号、Secret 脱敏）、确定性 Tool Policy（禁用清单 / 调用预算 / 副作用与显式审批）、Approval 与 JSONL 审计、Process Isolation Adapter（明确标注：非强 OS 沙箱）
- **持久执行（Durable Execution）**：可序列化的 `AgentExecutionState`、SQLite Durable Queue、Lease + 乐观版本、持久审批（跨进程恢复）、幂等记录与对账（`STARTED` / `COMPLETED` / `UNCERTAIN`）、崩溃恢复、取消、跨 Worker Trace 传播、进程内结构化并发（`asyncio.TaskGroup`）
- **商业平台（Commercial Platform）**：Tenant / Plan / API Key（高熵生成，库里只存 HMAC 摘要）/ Principal、API Scope 与 Tool Permission 分离、Quota（并发 Run / 每日 Run / 月 Token / 月 Tool Call）、Usage Ledger 与幂等事件、Usage Reconciler、Plan Snapshot 冻结、Billing Preview（整数 micro-USD + Decimal）、Admin Control Plane API、对象级授权（越权返回 404 而非 403）、RFC 9457 `application/problem+json`、FastAPI HTTP Surface 与 Lifespan 托管 Worker / Reconciler

应用层有两条并存的执行路径：`PersistentAgentService`（Immediate Mode，把运行器与持久化编排在一起，支持多轮会话）与 `DurableAgentService` + `DurableWorkerPool`（Durable Mode，把 Run 交给持久状态机由 Worker 分段推进）；两者之上叠加 `CommercialPlatformService`（Control Plane，只包裹不侵入 Runtime）。模型层通过 Provider 适配，目前支持 DeepSeek（chat 接口）与 OpenAI（responses 接口），可平滑替换。观测能力以横切方式注入各子系统，不改动既有业务逻辑。

## 已实现能力（Phase 1–10）

| 模块 | 阶段 | 能力 |
| --- | --- | --- |
| `harness/runner.py` | P1·P7·P10 | `AgentRunner` 主循环：生成 → 工具执行 → 结果回传，直至无调用或达到步数上限；`agent.loop` span。Phase 10 追加 `create_execution()` / `advance()`，把同一条循环拆成可持久化、可从任意 Worker 恢复的单步推进 |
| `harness/providers` | P1·P7·P11 | `DeepSeekProvider`（**默认模型 Provider**，chat 接口 + 本地历史续接）、`OpenAIProvider`（responses 接口，保留为可切换实现）；两者同构，均为异步 `generate` 并采集用量（tokens）与耗时指标 |
| `harness/tools` | P2·P7·P9·P10 | 统一 `Tool`（JSON Schema 输入）、`tool_from_pydantic` 工厂、注册表、执行器（校验 → 权限 → 安全策略 → 中间件 → 超时/重试 → 统一结果）；Phase 2 `ToolMiddleware` 恢复，Phase 10 新增 `idempotency.py`（幂等记录协议） |
| `harness/context` | P3 | `TokenBudget` 预算、`ApproxTokenCounter` 估算、`ContextPolicy` + `sources`（恢复）、`ContextBuilder` 分区组装指令 + 历史窗口与超预算裁剪 |
| `harness/state` | P4 | Conversation / Run / Step / Checkpoint / RuntimeEvent 模型、ID 生成 |
| `harness/persistence` | P4·P7·P10 | 完整 SQLite 建表脚本（含 Durable Tables）、Repository 仓储（含会话历史 `list_recent`）、UnitOfWork 事务边界 + `persistence.transaction` span；WAL 与迁移兼容 |
| `harness/retrieval` | P5·P7·P11 | 文档加载 / 字符切分 / 稳定 ID / 嵌入（**默认 `QwenEmbeddingProvider`**，`OpenAIEmbeddingProvider` 保留）/ 向量存储（Chroma）/ 稠密检索 / 重排 / 证据投影；`retrieval.search` span 与检索指标 |
| `harness/mcp` | P6·P7 | MCP 网关（HTTP·STDIO）、工具发现与适配、工具策略、资源读取、可选服务器降级；`mcp.tool.call` span 与 MCP 指标 |
| `harness/observability` | P7·P11 | OTel 引导（Console / File / OTLP 导出）、`Observability.span` 封装、`HarnessMetrics` 指标集（Phase 11 追加 platform 认证失败 / 配额拒绝 / 用量事件指标）、结构化 JSON 日志、模型成本核算、`shutdown_observability()` 冲刷 |
| `harness/evaluation` | P8·P11 | `EvaluationRunner` 评测编排、JSONL 数据集加载与格式校验、确定性评估器（答案包含 / 必需工具 / 禁止工具 / 最大步数）、可选 LLM Judge（**默认 `DeepSeekJudgeEvaluator`**；`OpenAIJudgeEvaluator` 完整保留）、JSON 报告与质量门、回归基线对比 |
| `harness/security` | P9 | `SecurityService` 输入 / 输出检查、Guard（长度 / Prompt Injection 信号 / Secret 脱敏）、`DefaultToolPolicy`（禁用 / 预算 / 审批）、`InMemoryApprovalStore` / `InMemoryRunBudgetStore`、`JsonlAuditSink`、`ProcessIsolationSandbox`（进程隔离 Adapter） |
| `harness/durable` | P10 | `DurableAgentService`、`DurableWorker` / `DurableWorkerPool`、`SQLiteDurableStore`、`SQLiteApprovalStore`、`SQLiteRunBudgetStore`、`SQLiteIdempotencyStore`、`AgentExecutionState` 序列化与 Trace Carrier |
| `harness/platform` | P11 | `CommercialPlatformService`（Control Plane，包裹 Durable Runtime）、`SQLitePlatformStore`（Tenant / Plan / API Key / Usage / Billing）、`ApiKeyManager`（HMAC 摘要 + Scope + 撤销）、`QuotaService`、`UsageReconciler`（幂等计量）、`BillingService`（Plan Snapshot + micro-USD）、`create_app`（FastAPI + Lifespan 托管 Worker）、`CommercialRuntime` |
| `harness/application.py` | P6·P7·P8 | `PersistentAgentService`：多轮会话 / 运行 / 消息落库与状态迁移，包住 Runner 并回传 `RunEvidence`（工具执行事实与模型用量） |
| `app_tools` | P2·P5·P9 | 示例工具：计算器（P2）、`search_knowledge_base` 知识检索（P5，多租户过滤）、`create_note` 副作用工具（P9，用于验证 Approval Gate） |
| `mcp_servers` | P6 | 演示 MCP Server：`multiply` / `get_order_status` 工具 + `guide://harness` 资源 |
| `evals` | P8 | 评测数据集（`evals/datasets/smoke.jsonl`）与评测报告（`evals/reports/`） |
| `scripts` | P5·P7·P8·P9·P11 | 知识导入、MCP 冒烟/检查、可观测性冒烟（`observability_smoke_test`）、评估冒烟（`evaluation_smoke_test`）、报告回归对比（`compare_eval_reports`）、安全冒烟（`security_smoke_test`）、平台冒烟（`platform_smoke_test`，不需要模型） |

## 路线图

| # | 阶段 | 状态 | 核心内容 |
| --- | --- | --- | --- |
| 1 | Harness Kernel | 已完成 | Agent 主循环、消息与结果模型、模型 Provider 抽象 |
| 2 | Production Tool Runtime | 已完成 | 工具注册 / 校验 / 权限 / 超时 / 重试 / 中间件 / 统一结果 |
| 3 | Context Engineering | 已完成 | Token 预算与裁剪、指令分区（工作状态 / 检索知识 / 外部上下文）、历史窗口 |
| 4 | State / Session / Persistence | 已完成 | Conversation / Run / Step / Checkpoint 持久化、SQLite 仓储、UnitOfWork 事务 |
| 5 | RAG | 已完成 | 文档加载与切分、向量化与索引、检索结果注入上下文 |
| 6 | MCP | 已完成 | MCP Server 网关与工具发现、统一适配、工具策略与降级 |
| 7 | Observability | 已完成 | OpenTelemetry 追踪与指标、结构化日志、模型用量与成本 |
| 8 | Evaluation | 已完成 | 评测数据集、自动化评分、回归基线 |
| 9 | Security | 已完成 | Guard（长度 / 注入信号 / Secret 脱敏）、确定性 Tool Policy、Approval、JSONL 审计、进程隔离 Adapter |
| 10 | Durable Execution | 已完成 | 持久状态机、SQLite 队列 + Lease + 乐观版本、持久审批、幂等与对账、崩溃恢复、取消、Trace 传播 |
| 11 | Commercial Platform | 已完成 | Tenant / Plan / API Key 认证与 Principal、Quota、Usage Ledger 与 Reconciler、Billing Preview、Admin Control Plane API、FastAPI HTTP Surface + Lifespan 托管 Worker |

## 快速开始

### 环境要求

- Python 3.11+
- 依赖由 `pyproject.toml` 声明：`openai`、`pydantic>=2`、`python-dotenv`、`jsonschema`、`chromadb`、`mcp[cli]`、`opentelemetry-api` / `opentelemetry-sdk` / `opentelemetry-exporter-otlp-proto-http`、`fastapi` / `uvicorn[standard]`（Phase 11 HTTP Surface，仅在最外层）（开发另需 `pytest`、`pytest-asyncio`、`httpx`、`ruff`、`mypy`）

### 安装

```bash
pip install -e ".[dev]"
```

### 配置 .env（可参考仓库内的 `.env.example`）

```env
# 对话模型(DeepSeek)
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 向量模型(阿里云 DashScope，RAG 检索用)
DASHSCOPE_API_KEY=sk-xxxx
DASHSCOPE_MODEL=text-embedding-v3
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# MCP 演示服务器地址(可选，默认 http://127.0.0.1:8000/mcp)
# 演示服务器只监听 IPv4 回环地址；请使用 127.0.0.1 而非 localhost，
# 否则客户端可能解析到 ::1 而导致工具发现失败（可选服务器会静默降级）。
DEMO_MCP_URL=http://127.0.0.1:8000/mcp

# 可观测性(Phase 7)
OTEL_MODE=console                                   # console / file / otlp
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318   # OTEL_MODE=otlp 时生效
OTEL_TELEMETRY_PATH=data/telemetry.log              # OTEL_MODE=file 时 span 与指标落盘路径
OTEL_LOG_PATH=data/logs.jsonl                       # OTEL_MODE=file 时结构化日志落盘路径
LOG_LEVEL=INFO                                      # 结构化 JSON 日志级别

# 安全与持久执行(Phase 9 / Phase 10)
HARNESS_DATABASE_PATH=data/harness.db
HARNESS_MAX_INPUT_CHARS=16000
HARNESS_MAX_OUTPUT_CHARS=32000
HARNESS_MAX_TOOL_CALLS_PER_RUN=16
HARNESS_DETECT_PROMPT_INJECTION=true      # Prompt Injection 仅记录信号
HARNESS_BLOCK_PROMPT_INJECTION=false      # 设为 true 则直接阻断
HARNESS_APPROVAL_FOR_SIDE_EFFECTS=true    # 副作用工具需要显式审批
HARNESS_DISABLED_TOOLS=                   # 逗号分隔的禁用工具清单
HARNESS_SECURITY_AUDIT_PATH=data/security_audit.jsonl
HARNESS_WORKER_COUNT=2                    # Durable Worker 数量
HARNESS_LEASE_SECONDS=120                 # Run 租约时长
HARNESS_POLL_SECONDS=0.5                  # Worker 轮询间隔

# 上下文预算(Phase 3)
MAX_CONTEXT_TOKENS=32000
RESERVED_OUTPUT_TOKENS=4000
RECENT_MESSAGE_LIMIT=20

# 商业平台(Phase 11)
# Pepper 必须稳定保存，不能每次启动随机变化，否则已发行的 API Key 全部失效。
HARNESS_API_KEY_PEPPER=
HARNESS_METERING_POLL_SECONDS=1.0
HARNESS_USAGE_SYNC_BATCH_SIZE=100
```

> MCP 演示服务器未启动时不影响启动：`required=False` 的可选服务器发现失败会自动降级。

### 模型与向量 Provider（同构可替换）

项目里**每一处 OpenAI 模型调用都有一个同构的 DeepSeek 实现**，并且实际调用点全部走 DeepSeek / Qwen（参数直接取 `.env` 中已有的 `DEEPSEEK_*` / `DASHSCOPE_*`）。OpenAI 实现被完整保留，可通过显式参数切回：

| 能力 | 默认（实际调用） | 保留的 OpenAI 实现 | 调用点 |
| --- | --- | --- | --- |
| 对话模型 | `DeepSeekProvider`（chat 接口，零参构造读 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL`） | `OpenAIProvider`（Responses 接口） | `main.py` `build_runtime()` |
| LLM Judge | `DeepSeekJudgeEvaluator`（chat 接口 + `json_object` 输出） | `OpenAIJudgeEvaluator`（Responses 接口 + 严格 `json_schema`） | `main.py eval --judge-model` |
| 向量模型 | `QwenEmbeddingProvider`（DashScope OpenAI 兼容模式，读 `DASHSCOPE_*`） | `OpenAIEmbeddingProvider` | `main.py` `build_runtime()` |

三者都遵循同一协议（`generate` / `evaluate` / `embed_documents` + `embed_query`），构造参数已对齐（`model` / `api_key` / `base_url` / `batch_size`），因此可以零参构造后直接互换，不需要改动 Runner、Retriever 或 Evaluator。两个 Judge 还共用同一套 Prompt 与评分契约（`score` 0–1 + `reason`），判定口径一致。

> **注意**：`OpenAIProvider` / `OpenAIJudgeEvaluator` / `OpenAIEmbeddingProvider` 需要 `OPENAI_API_KEY` 才能构造；本仓库默认不配置它，因此这三条路径不会在缺省运行中被触发。

### 运行入口

`main.py` 提供 8 个子命令，**不带子命令时默认走最新能力 `api`**（Phase 11 起的有意入口变化，Phase 10 的 `durable-chat` 完整保留）：

| 子命令 | 说明 |
| --- | --- |
| `python main.py` / `python main.py api` | Phase 11 Commercial Platform API（默认 `127.0.0.1:8008`，Lifespan 托管 Durable Worker Pool + Usage Reconciler） |
| `python main.py api --host 0.0.0.0 --port 8008` | 指定监听地址与端口 |
| `python main.py platform-init` | 初始化套餐 / 租户并发行首批 API Key（明文只打印一次） |
| `python main.py platform-check` | Phase 11 无模型验收（多租户 / Auth / Quota / Metering / Billing） |
| `python main.py durable-chat` | Phase 10 Durable Agent（持久状态机 + Worker Pool） |
| `python main.py chat` | Phase 1–9 Immediate Agent（兼容入口） |
| `python main.py durable-check` | Phase 10 无网络验收（Scripted Model，不需要 API Key） |
| `python main.py security-check` | Phase 9 安全验收（审批 / 脱敏 / 注入信号 / 进程隔离） |
| `python main.py eval` | Phase 8 Evaluation Suite |

组装流程：初始化遥测 → SQLite（WAL + Phase 1–9 Schema + Durable Schema）→ Durable Store / Approval / Budget / Idempotency → Security → 工具注册（计算器 / `create_note` / RAG / MCP）→ `ToolExecutor`（Middleware + Security + Idempotency）→ `AgentRunner` → Immediate 与 Durable 两条应用路径。会话、运行状态与消息都会持久化，多轮输入续接同一会话。

三条不需要 API Key 的验收命令：

```bash
# 预期：第一次执行 WAITING_APPROVAL → 审批恢复 COMPLETED
python main.py durable-check

# 预期：未审批 APPROVAL_REQUIRED → 审批后 SUCCESS
python main.py security-check

# 预期：Platform Check（多租户/Auth/Quota/Metering/Billing）通过。
python main.py platform-check
```

### 商业平台（Phase 11）

先设置一个**稳定**的 Pepper，再初始化平台，然后启动 API：

```powershell
# Pepper 必须长期保存；每次启动随机变化会让已发行的 API Key 全部失效。
$env:HARNESS_API_KEY_PEPPER = "请换成你自己的高熵长期 Secret"

# 创建套餐（starter_v1 / pro_v1 / operator_v1）、租户（_platform / tenant_demo）并发行 API Key。
# 明文 API Key 只打印这一次，请立即保存到 Secret Manager。
python main.py platform-init

# 启动 Commercial Platform API（默认 http://127.0.0.1:8008）
python main.py api
```

启动后可访问 `http://127.0.0.1:8008/docs` 查看 OpenAPI UI（开发阶段可直接作为 Admin API 操作台）。

| 端点 | 所需 Scope | 说明 |
| --- | --- | --- |
| `GET /healthz` | 无 | 健康检查（含版本号） |
| `GET /v1/me` | 任意有效 Key | 返回 Tenant、API Key ID 与 Scope |
| `POST /v1/runs` | `runs:create` | 提交 Run（202 Accepted，由 Worker 异步推进） |
| `GET /v1/runs/{run_id}` | `runs:read` | 查询 Run；跨租户访问返回 **404**（对象级授权不泄露存在性） |
| `POST /v1/runs/{run_id}/approve` · `/cancel` | `runs:approve` · `runs:cancel` | 审批与取消 |
| `GET /v1/usage?start=&end=` | `usage:read` | 查询用量账本（ISO8601 区间） |
| `GET /v1/billing/preview` | `billing:read` | 按当前 UTC 月做计费预览 |
| `GET /v1/admin/plans` · `/v1/admin/tenants` 等 | `platform:admin` | Admin Control Plane（租户、套餐、发行 Key、暂停租户、切换套餐） |

**关键约束**：Tenant、Plan、Tool Permission、Quota 都由服务端从 API Key 与数据库解析（`Principal` → `Tenant.plan_id` → `Plan.tool_permissions`），**客户端不能提交 `tenant_id` 或 `permissions`**——否则等于让调用方自己给自己发权限。

无模型的平台冒烟：

```bash
# 覆盖 Platform Schema / API Key 发行与认证 / Tenant / Plan / Quota / Usage / Billing Preview
python -m scripts.platform_smoke_test
```

> MCP 演示服务器未启动时不影响启动：`required=False` 的可选服务器发现失败会自动降级。

### 运行评测（Phase 8）

`eval` 子命令：

```bash
# 运行评测数据集并写出报告（默认 evals/datasets/smoke.jsonl）
python main.py eval

# 指定数据集 / 套件名 / 报告路径 / 质量门阈值
python main.py eval --dataset evals/datasets/smoke.jsonl --suite smoke \
  --report evals/reports/latest.json --min-pass-rate 0.8 --min-average-score 0.8

# 追加 LLM Judge（默认走 DeepSeek，参数取自 .env 的 DEEPSEEK_*）
python main.py eval --judge-model deepseek-flash

# 需要时切回 OpenAI Responses 接口实现（需要 OPENAI_API_KEY）
python main.py eval --judge-model gpt-4o-mini --judge-provider openai
```

评测流程：加载 JSONL 数据集 → 每个 Case 使用独立 Conversation 跑真实 Agent → 确定性评估器评分（可叠加 LLM Judge）→ 写出 JSON 报告 → 质量门校验未达标则以非零退出码结束（可直接用于 CI 阻断）。

报告字段包含每个 Case 的输入、实际输出、步数、**工具执行证据**（`evidence.tool_executions`）与各评估器的分数和原因，便于定位失败原因。

回归对比（与基线报告比较，通过率或平均分下降超阈值则非零退出）：

```bash
python -m scripts.compare_eval_reports \
  evals/reports/baseline.json evals/reports/latest.json
```

运行评测前请确认演示 MCP 服务器已启动（`python -m mcp_servers.demo_server`），否则 `mcp_multiply` 这类依赖远端工具的用例会因可选服务器降级而失败：

```bash
# 单独的评测冒烟（不依赖真实模型）
python -m scripts.evaluation_smoke_test
```

### 可观测性（Tracing / Metrics / Logs）

Phase 7 起，运行链路可输出 OpenTelemetry 遥测（span 与指标）及结构化 JSON 日志。导出方式由 `OTEL_MODE` 选择：`console`（默认，打印到终端）、`file`（写入本地文件）、`otlp`（导出到 Collector）。

```bash
# 默认：Console 遥测（span / 指标直接打印在终端）
python main.py
```

```powershell
# file 模式：遥测与结构化日志落盘，控制台只保留对话与工具输出
$env:OTEL_MODE = "file"
$env:OTEL_TELEMETRY_PATH = "data/telemetry.log"   # span + 指标（UTF-8 追加）
$env:OTEL_LOG_PATH = "data/logs.jsonl"            # 结构化 JSON 日志
python main.py
```

```powershell
# OTLP 模式：导出到 OpenTelemetry Collector（默认 http://localhost:4318）
$env:OTEL_MODE = "otlp"
python main.py
```

> 交互式 `chat` 下 span / 指标 / JSON 日志会持续刷屏，把对话和工具调用淹没，建议使用 `OTEL_MODE=file`。进程退出时（包括质量门失败等异常路径）会自动 `force_flush` 并关闭遥测，不会丢失最后一批数据。

- 覆盖的 span：`agent.loop` → `gen_ai.generate` / `tool.execute` / `retrieval.search` / `mcp.tool.call` / `persistence.transaction`
- 指标集：agent / tool / mcp 调用与错误计数、model input/output token、各环节耗时直方图、检索结果数
- 结构化日志自动携带 `trace_id` / `span_id`；模型成本可由 `CostCalculator` 按价目表核算
- 仓库内提供 OTel Collector 参考配置（`harness/observability/` 下的 YAML，OTLP 接收 → debug 导出）

无 Collector 的快速冒烟：

```bash
python -m scripts.observability_smoke_test
```

### 演示与诊断脚本

`scripts/` 下提供多个脚本（运行前请先修改脚本内的路径或服务器地址）：

```bash
# 知识加载与切分演示：读取文本文件并打印切分结果
python -m scripts.ingest_knowledge

# MCP：检查演示服务器的工具清单与调用结果（需先启动 MCP 服务器）
python -m scripts.inspect_mcp_server

# MCP：本地工具 + MCP 工具的端到端冒烟测试（需先启动 MCP 服务器）
python -m scripts.smoke_test
```

### 运行测试

```bash
python -m pytest tests -q
```

## 运行流程

```
用户输入 (可携带 conversation_id 续接多轮会话)
   │
   ▼
PersistentAgentService.ask ──► 会话/运行/消息落库 → AgentRunner.run (agent.loop span)
   │                                    │
   │          ContextBuilder 组装指令(系统指令 + 工作状态 + 检索知识/外部上下文)
   │          + 历史窗口与 Token 预算裁剪
   │                                    │
   │                                    ▼
   │                    模型 generate(gen_ai.generate span + token 指标)
   │                        │
   │              无工具调用 ──► 返回最终文本(落库)
   │                        │
   │              有工具调用
   │                        ▼
   │              ToolExecutor.execute ──► 校验 → 权限 → 超时/重试
   │                        (tool.execute span + 调用/错误/耗时指标)
   └──── 工具结果回传 ◄──────┘   (循环直至无调用或达到 max_steps)

贯穿：trace 上下文（span）+ 指标（counter / histogram）+ 结构化 JSON 日志
```

Phase 11 的 HTTP 路径（Control Plane 包裹 Runtime，不复制执行内核）：

```
POST /v1/runs
   │
   ▼
APIKeyHeader ──► ApiKeyManager.authenticate（HMAC 摘要比对）
   │
   ▼
Principal ──► Tenant ACTIVE? ──► Scope runs:create?
   │
   ▼
Plan ──► QuotaService（并发 Run / 每日 Run / 月 Token / 月 Tool Call）
   │
   ▼
DurableAgentService.submit ──► platform_run_accounts 冻结 Plan Snapshot
   │                                └──► run_submitted Usage Event
   ▼
Durable Worker ──► Phase 1–10 Agent Runtime ──► Terminal State
   │
   ▼
UsageReconciler ──► input_tokens / output_tokens / tool_calls（幂等 event_key）
   │
   ▼
GET /v1/usage · GET /v1/billing/preview
```

## 项目结构

以下为 Phase 1–10 已落地的结构：

```
mini-harness/
├── main.py                    # CLI 入口（api / platform-init / platform-check / durable-chat / chat / durable-check / security-check / eval）
├── pyproject.toml             # 项目元数据、依赖声明、pytest / ruff / mypy 配置
├── .env.example               # 环境变量示例（不含任何真实密钥，`.env` 被 .gitignore 排除）
├── harness/
│   ├── models.py              # ToolCall / ModelUsage / ModelResult / RunResult / RunEvidence
│   ├── runner.py              # AgentRunner：run() 即时循环 + create_execution()/advance() 分段推进
│   ├── application.py         # PersistentAgentService：多轮会话 + 持久化编排 + RunEvidence 回传
│   ├── tools/                 # 工具运行时（定义 / 工厂 / 校验 / 注册 / 中间件 / 幂等 / 执行 / 结果）
│   ├── context/               # 上下文工程（Token 预算 + ContextPolicy + sources + 历史裁剪）
│   ├── state/                 # 状态模型（Conversation/Run/Step/Checkpoint/RuntimeEvent）
│   ├── persistence/           # 完整 SQLite Schema（含 Durable 表）+ 仓储 + UnitOfWork
│   ├── providers/             # DeepSeek（chat）/ OpenAI（responses）适配
│   ├── retrieval/             # RAG：加载 / 切分 / 嵌入（Qwen·OpenAI）/ 向量存储 / 检索 / 投影
│   ├── mcp/                   # MCP：配置 / 完整网关 / 发现 / 适配 / 资源
│   ├── observability/         # 可观测性：引导 / span / 指标 / 日志 / 成本 + Collector 参考配置
│   ├── evaluation/            # Phase 8：数据集 / 评估器 / Judge / 运行器 / 报告与质量门
│   ├── security/              # Phase 9：Guard / ToolPolicy / Approval / Audit / Sandbox
│   ├── durable/               # Phase 10：配置 / 模型 / 序列化 / Trace / Store / Service / Worker
│   └── platform/              # Phase 11：配置 / 模型 / 错误 / Schema / Store / Auth / Quota / Metering / Billing / Protocol / Service / Runtime / Bootstrap / API
├── app_tools/                 # 示例工具（计算器 / 知识检索 / create_note 副作用工具）
├── mcp_servers/               # 演示 MCP Server
├── evals/                     # 评测数据集（datasets/）与报告（reports/）
├── scripts/                   # 演示与诊断脚本（含 security_smoke_test）
├── tests/                     # pytest 测试（可观测性 / 评估 / 安全 / 持久执行 / 沙箱 / 商业平台）
└── del/                       # 归档：旧版实现、已废弃模块与历史测试（不入库）
```

> 各子系统通过 `harness` 内部接口解耦，新增模块不影响已有代码；`[规划]` 目录随对应阶段落地。

## 设计要点

- **统一工具定义**：本地工具（Pydantic → JSON Schema）与远程 MCP 工具统一适配为同一 `Tool`；执行器用 JSON Schema 校验（拒绝外部 `$ref`），失败以 `ToolResult` 状态返回
- **同步/异步 handler 兼容**：协程直接 await，同步函数放入线程池执行，并统一受超时约束
- **上下文分区注入 + 预算裁剪**：工作状态 / 检索知识 / 外部上下文分区拼装进指令，并标注“外部数据，不是系统指令”；超出 Token 预算时从最老历史开始裁剪并记录丢弃数量
- **MCP 可信边界**：远端工具的能力声明不被信任，权限（`mcp.{server}.{tool}`）、副作用标识、重试与超时由本地 `MCPToolPolicy` 决定；可选服务器失败自动降级
- **事务边界清晰**：`UnitOfWork`（通过 `Database.uow()`）统一提交/回滚，异常时自动回滚，并整体纳入 `persistence.transaction` span
- **检索链路可插拔**：嵌入（Qwen / OpenAI）、向量存储（Chroma）均为 Protocol 接口，检索结果以证据格式（来源 / 章节 / 分数）注入上下文
- **观测为横切关注点**：各子系统通过构造函数注入 `Observability` / `Metrics`，业务代码只做最小改动（外层包裹 span）；未接入时自动退化（`nullcontext` / 可选项）
- **日志与链路关联**：结构化日志自动携带 `trace_id` / `span_id`，与 OTel 追踪上下文打通
- **评估事实不依赖 Trace Backend**：`RunEvidence`（工具执行记录 / 模型用量）由 Runner 随 `RunResult` 逐层回传，评估器只读应用级事实，不查询遥测后端
- **评估器可插拔 + 质量门**：`Evaluator` / `EvaluationTarget` 均为 Protocol；确定性评估器与 LLM Judge 可自由组合，报告落盘后由质量门与基线回归对比决定是否阻断 CI
- **Durable State 而非协程状态**：内存 Coroutine 可以消失，但持久执行状态不能；`AgentExecutionState` 可序列化入库，Worker 通过 `create_execution()` / `advance()` 从确切状态继续（**Resume ≠ Retry**）
- **Lease + 乐观版本双重保护**：Lease 避免 Worker 死亡后永久占用；保存时以 `version` + `lease_owner` 作为条件（`WHERE version = expected_version AND lease_owner = worker_id`）防止 Stale Worker 覆盖新状态，冲突抛 `DurableConflictError`
- **不轻率承诺 Exactly Once**：跨系统副作用以 `STARTED` / `COMPLETED` / `UNCERTAIN` 三态记录；非幂等副作用在 `STARTED` 后崩溃进入 `WAITING_RECONCILIATION`，而不是盲目重试
- **Trace 跨 Worker 显式传播**：Durable Queue 持久化 `trace_carrier_json`，Worker Claim 后 `extract` → 起 `durable.worker.segment` span → 状态转换 → 重新 `inject` 并 checkpoint，不依赖 ContextVar 自然传播
- **安全是执行前的确定性关卡**：`DefaultToolPolicy` 在工具真正执行前决定 ALLOW / BLOCK / APPROVAL_REQUIRED；模型与远端工具的能力声明都不被信任
- **沙箱能力边界写清楚**：`ProcessIsolationSandbox` 只提供 `shell=False`、可执行文件 allowlist、最小环境变量、超时与输出上限，**不是强 OS 沙箱**；执行不可信代码应替换为 Container / VM / AppContainer 等强隔离后端
- **Commercial Platform 是 Control Plane，不是第二套 Runtime**：`AgentRunner` 没有增加任何 `tenant` / pricing / API key / billing 分支；依赖方向固定为 `Platform → Durable Runtime → AgentRunner`，商业逻辑包裹 Runtime 而不污染 Runtime
- **身份四层分离**：`User`（终端使用者）、`API Key`（高熵凭据，库里只存 HMAC 摘要）、`Principal`（一次认证后的可信身份）、`Tenant`（商业隔离与计费主体）是四个不同概念；`API Scope`（能否调用某个 HTTP 端点）与 `Tool Permission`（Agent 能执行哪个工具）也必须分开
- **客户端不提交权限**：`POST /v1/runs` 只接受 `input`；Tenant 由 API Key 解析，Tool Permission 由 `Plan.tool_permissions` 决定，让套餐 Entitlement 成为服务端事实
- **用量账本是 Append / Idempotent Fact**：`Usage Ledger` 以稳定 `event_key` 写入，`UsageReconciler` 从 Durable Run 的真实 `RunEvidence` 异步同步，重复执行不会重复计量；`Run Submitted / Completed / Failed / Cancelled` 都计量
- **Plan Snapshot 冻结归属**：Run 提交时把当时生效的 `plan_id` 冻结进 `platform_run_accounts`，之后租户升级套餐不会改写历史用量归属
- **计费用整数 micro-USD + Decimal**：避免浮点误差，可审计；当前只做 Preview / 内部账本计算，Provider（Stripe / ERP）通过 `BillingExporter` 保持可插拔
- **对象级授权返回 404 而非 403**：越权访问别人的 `run_id` 时不泄露对象是否存在（OWASP API1 BOLA），错误统一为 RFC 9457 `application/problem+json` 并携带 `request_id`
- **Provider 同构替换**：模型（`DeepSeekProvider` ↔ `OpenAIProvider`）、Judge（`DeepSeekJudgeEvaluator` ↔ `OpenAIJudgeEvaluator`）、向量（`QwenEmbeddingProvider` ↔ `OpenAIEmbeddingProvider`）三对实现共享同一协议与同一套构造参数，默认使用 DeepSeek / Qwen，OpenAI 实现完整保留；替换 Provider 不需要改动 Runner、Retriever、Evaluator 任何一行

## 开发状态

项目处于活跃开发中，接口与目录结构可能随阶段推进调整。各阶段完成后会同步更新本文档的路线图与能力清单（详见 [CHANGELOG.md](CHANGELOG.md)）。

- 测试覆盖随重构调整：当前 `tests/` 覆盖可观测性 / 评估 / 安全 / 持久执行 / 沙箱 / 商业平台（`test_platform_auth_quota` / `test_platform_tenant_isolation` / `test_platform_metering` / `test_platform_api`），历史测试位于 `del/tests/` 归档
- 在无法创建临时目录的受限环境（部分容器 / 沙箱）中，依赖 pytest `tmp_path` 的用例会因权限问题报错，这属于环境限制而非代码缺陷
- **SQLite 的真实商业边界**：`Durable Store` 与 `Platform Store` 目前共用同一个 SQLite 文件，WAL 依赖同主机共享内存，因此只适用于**本地优先产品 / 单节点 SaaS MVP / 小团队内部服务 / 教学与 Preview Release**；不应声称支持多 Region、多节点 HA 或百万 QPS Control Plane。真正规模化应把 `PlatformStore`、`DurableStore`、`Usage Ledger` 迁移到 PostgreSQL，并把 HTTP Rate Limit 放到 Gateway / Redis
- **当前明确遗留**：① 尚无严格的分布式 HTTP Rate Limiter（业务 Quota 已完成）；② Token Quota 是「完成后计量 + 下次请求阻止」，严格 Prepaid 需要 Token Reservation / Model-call-level Budget；③ Usage Ledger 与 Durable Submit 之间不是跨领域原子事务（靠稳定 `event_key` + 对账解决重复，支付级系统应上 Transactional Outbox）；④ Billing 只是 Preview / 内部账本计算，尚无 Tax / Invoice Finalization / Refund / Credit Note / Payment Collection / Stripe Webhook；⑤ API Key 是第一版 M2M Auth，尚无 OAuth2 / 用户级会话；⑥ Admin Control Plane API 已完成，但没有品牌化 Dashboard UI（开发期用 `/docs`）
- `.env`、`data/` 与 `del/` 已加入 `.gitignore`，不会提交到仓库；仓库只提供不含密钥的 `.env.example`。评测报告中的 `evals/reports/latest.json` 为每次运行产物，同样不入库（`baseline.json` 作为回归基线入库）
- API Key 明文**只在 `platform-init` 打印一次**，数据库只保存 HMAC 摘要；`HARNESS_API_KEY_PEPPER` 必须长期稳定保存，否则已发行的 Key 全部失效

## 贡献

欢迎参与共建！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境、提交规范与 PR 流程。

## 更新日志

版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
