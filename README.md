# mini-harness

> 一个分阶段演进的迷你 LLM Agent 框架：工具运行时、上下文工程、状态持久化

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Version](https://img.shields.io/badge/Version-v0.13.0-purple)
![Status](https://img.shields.io/badge/Status-Phase%2013%20%28Streaming%20Workbench%29%20Done-brightgreen)

## 目录

- [简介](#简介)
- [快速开始](#快速开始)
- [声明式配置 harness.toml](#声明式配置-harnessToml)
- [可选组件与 Extras](#可选组件与-extras)
- [开发者 CLI](#开发者-cli)
- [本地 HTTP Server](#本地-http-server)
- [插件](#插件)
- [已实现能力](#已实现能力phase-113)
- [路线图](#路线图)
- [运行流程](#运行流程)
- [项目结构](#项目结构)
- [设计要点](#设计要点)
- [开发状态](#开发状态)
- [贡献](#贡献)
- [更新日志](#更新日志)
- [许可证](#许可证)

## 简介

mini-harness 是一个分阶段演进的 LLM Agent 框架（Harness），目标是从内核出发，逐步补全一个生产级 Agent 系统所需的全部基础设施。项目按 13 个阶段推进，**Phase 1–13 全部完成（v0.13.0）**。

从 v0.10.0 起采用一条固定规则：**旧能力 + 新能力 = 新版本**，不再用「新增片段」覆盖「旧完整文件」而导致既有能力消失。

**Phase 12 是收敛性重构，不是新增能力。** 它解决的是「组合根泄漏」：此前启动一个 Agent 需要先理解并手工组装 `SQLiteDurableStore` / `SecurityService` / `RetrievalPipeline` / `MCPManager` / `ContextBuilder` / `AgentRunner` 等二十多个类。现在这些类**仍然全部存在**，但收敛进内部组合根，开发者只需要一个门面：

```python
from harness import HarnessApp

app = HarnessApp()

@app.tool
def add(a: float, b: float) -> float:
    """计算两个数字的加法。"""
    return a + b

if __name__ == "__main__":
    app.cli()
```

同时 Phase 12 把「商业级」明确等价于 **Production-grade engineering（可商用的软件工程规范）**，而不是「必须有收费与套餐」。Phase 11 的 Tenant / Usage Ledger / Billing Preview 能力完整保留，但降为 **Optional Platform Extension**，不再是 OSS 默认启动的前置条件。

**Phase 13 把「Harness 能力」落成一个可以直接用的本地工作台**，由三件事组成：① 模型输出改为**真实流式**，进程内 `RunEventBroker` 加 SSE 端点把 `model.delta` / `tool.start` / `run.waiting` 实时推给界面，前端从「提交后轮询」变成「边跑边看」；② 业务工具整体下沉到应用层 `app_tools/`，框架不再内置任何业务工具，工作区目录通过 `ToolContext` 注入，因此工具可以脱离数据库直接单元测试；③ 产品定位收敛为**本地优先的个人工作台**——配额与调用预算不再拦截个人运行。升级前请读 [0.12 → 0.13 迁移说明](docs/migration-v0.12-to-v0.13.md)。

已完成的 Phase 1–13 把「模型会调用工具」与「谁可以使用它」拆解成十个可独立演进的子系统：

- **工具运行时**：统一工具定义（JSON Schema）、Pydantic → Schema 工厂、JSON Schema 参数校验（拒绝外部 `$ref`）、权限检查、超时控制、重试策略、统一结果对象
- **上下文工程**：Token 预算与安全边距、分区组装指令（系统指令 + 工作状态 + 检索知识 + 外部上下文）、历史窗口与超预算裁剪（记录丢弃消息数）
- **状态与持久化**：Conversation / Run / Step / Checkpoint / RuntimeEvent 状态模型、SQLite 仓储（Repository）+ 工作单元（UnitOfWork）事务、多轮会话历史回放
- **检索增强（RAG）**：文档加载与字符切分（带重叠）、稳定 ID、向量化（Qwen / OpenAI 嵌入）、向量存储（Chroma）、稠密检索与可插拔重排、证据化结果投影
- **MCP 集成**：MCP Server 配置与网关（HTTP / STDIO 双传输）、工具发现与统一适配（权限 / 策略 / 元数据）、资源读取、可选服务器降级
- **可观测性**：OpenTelemetry 追踪（span）与指标（计数 / 直方图）、结构化 JSON 日志、模型用量与成本核算、Console / OTLP 双导出
- **评估（Evaluation）**：JSONL 评测数据集与格式校验、确定性评估器（答案包含 / 必需工具 / 禁止工具 / 最大步数）、可选 LLM Judge（参考答案 / 评分标准）、评测报告落盘与质量门、基线回归对比
- **安全（Security）**：输入 / 输出 Guard（长度、Prompt Injection 信号、Secret 脱敏）、确定性 Tool Policy（禁用清单 / 副作用与显式审批）、Approval 与 JSONL 审计、Process Isolation Adapter（明确标注：非强 OS 沙箱）。**注意**：0.13 起 Tool Call Budget 不再拦截运行（`max_tool_calls_per_run` 默认 `None`）
- **持久执行（Durable Execution）**：可序列化的 `AgentExecutionState`、SQLite Durable Queue、Lease + 乐观版本、持久审批（跨进程恢复）、幂等记录与对账（`STARTED` / `COMPLETED` / `UNCERTAIN`）、崩溃恢复、取消、暂停与恢复、附加指令注入、跨 Worker Trace 传播、进程内结构化并发（`asyncio.TaskGroup`）
- **商业平台（Commercial Platform）**：Tenant / Plan / API Key（高熵生成，库里只存 HMAC 摘要）/ Principal、API Scope 与 Tool Permission 分离、Usage Ledger 与幂等事件、Usage Reconciler、Plan Snapshot 冻结、Billing Preview（整数 micro-USD + Decimal）、Admin Control Plane API、对象级授权（越权返回 404 而非 403）、RFC 9457 `application/problem+json`、FastAPI HTTP Surface 与 Lifespan 托管 Worker / Reconciler。0.13 起 **Quota 退化为兼容门面**（`QuotaDecision` 恒为 `UNLIMITED`）：用量照常计量与记账，但不再有配额会拒绝提交
- **流式对话工作台（Local Workbench）**：进程内 `RunEventBroker`（按 `run_id` 广播 + 最近 32 次 Run 的回放缓冲）、SSE 端点 `GET /v1/runs/{run_id}/stream`、真实流式模型输出、工作区 / 会话 / 知识库的本地端点，以及「创建工作区 + 对话」的单页前端

应用层有两条并存的执行路径：`PersistentAgentService`（Immediate Mode，把运行器与持久化编排在一起，支持多轮会话）与 `DurableAgentService` + `DurableWorkerPool`（Durable Mode，把 Run 交给持久状态机由 Worker 分段推进）；两者之上叠加 `CommercialPlatformService`（Control Plane，只包裹不侵入 Runtime）。模型层通过 Provider 适配，目前支持 DeepSeek（chat 接口）与 OpenAI（responses 接口），可平滑替换。观测能力以横切方式注入各子系统，不改动既有业务逻辑。

## 已实现能力（Phase 1–13）

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
| `harness/observability` | P7·P11 | OTel 引导（Console / File / OTLP 导出）、`Observability.span` 封装、`HarnessMetrics` 指标集（Phase 11 追加 platform 认证失败 / 用量事件指标；`platform_quota_denials` 计数器保留但 0.13 起不再自增）、结构化 JSON 日志、模型成本核算、`shutdown_observability()` 冲刷 |
| `harness/evaluation` | P8·P11 | `EvaluationRunner` 评测编排、JSONL 数据集加载与格式校验、确定性评估器（答案包含 / 必需工具 / 禁止工具 / 最大步数）、可选 LLM Judge（**默认 `DeepSeekJudgeEvaluator`**；`OpenAIJudgeEvaluator` 完整保留）、JSON 报告与质量门、回归基线对比 |
| `harness/security` | P9·**P13** | `SecurityService` 输入 / 输出检查、Guard（长度 / Prompt Injection 信号 / Secret 脱敏）、`DefaultToolPolicy`（禁用 / 审批）、`InMemoryApprovalStore` / `InMemoryRunBudgetStore`、`JsonlAuditSink`、`ProcessIsolationSandbox`（进程隔离 Adapter）。**0.13 起 Tool Call Budget 不再拦截运行**（`consume()` 保留为恒 `True` 的兼容门面） |
| `harness/durable` | P10·**P13** | `DurableAgentService`、`DurableWorker` / `DurableWorkerPool`、`SQLiteDurableStore`、`SQLiteApprovalStore`、`SQLiteRunBudgetStore`（兼容门面）、`SQLiteIdempotencyStore`、`AgentExecutionState` 序列化与 Trace Carrier；0.13 追加暂停 / 恢复、附加指令注入与提交时的 step 0 检查点 |
| `harness/platform` | P11·**P13** | `CommercialPlatformService`（Control Plane，包裹 Durable Runtime）、`SQLitePlatformStore`（Tenant / Plan / API Key / Usage / Billing）、`ApiKeyManager`（HMAC 摘要 + Scope + 撤销）、`UsageReconciler`（幂等计量）、`BillingService`（Plan Snapshot + micro-USD）、`create_app`（FastAPI + Lifespan 托管 Worker）、`CommercialRuntime`。0.13 起 `QuotaService` 退化为恒 `UNLIMITED` 的兼容门面，**用量照常记录但不再拒绝提交** |
| `harness/streaming.py` | **P13** | `RunEventBroker`：按 `run_id` 广播运行事件并保留最近 32 次 Run 的回放缓冲，`open()` 原子返回「历史缓冲 + 实时队列」，因此「提交任务」与「打开事件流」之间的竞态既不丢事件也不重复 |
| `harness/ui` | P11 | 对话工作台的静态托管（`STATIC_DIRECTORY`）与独立预览入口（`python -m harness.ui`，仅文件服务）；`static/` 为 Vue 3 + TypeScript 前端的**构建产物**，源码在 `frontend/` |
| `harness/app` | **P12**·**P13** | **开发者门面层**：`HarnessApp`（`@app.tool` / `add_tool` / `use` / `build` / `ask` / `submit` / `chat` / `serve` / `cli`）、`HarnessConfig` + `load_config`（TOML + `${VAR}` 展开）、`tooling.to_tool`（typed callable → Tool）、`plugins`（Entry Point 发现）、`assembly`（内部组合根）、`server`（Local HTTP + loopback 保护）、`checks`、`noop`（Noop Observability / Metrics / Security）。P13 追加 `desktop.py`（工作区 / 会话 / 知识库 / 控制的服务层）与 `desktop_api.py`（仅 Local 模式挂载的 `/v1/workspaces`、`/v1/sessions`、`/v1/runs/{id}/stream` 等路由） |
| `harness/cli.py` | **P12** | `mini-harness` 命令行入口：`chat` / `serve` / `doctor` / `plugins` / `security-check` / `durable-check` / `eval` / `platform-init` |
| `frontend` | P11·**P13** | 工作台前端源码：Vue 3 `<script setup>` + Pinia + Vite，只做「工作区创建 + 工作区内对话」两件事——Markdown 渲染（`marked` + `DOMPurify`）、SSE 逐字流式显示、工具调用卡片与批准/拒绝；`npm run test` 用 vitest + jsdom 覆盖流式增量与 Markdown |
| `harness/application.py` | P6·P7·P8 | `PersistentAgentService`：多轮会话 / 运行 / 消息落库与状态迁移，包住 Runner 并回传 `RunEvidence`（工具执行事实与模型用量） |
| `main.py` | **P12** | 项目入口，13 行：加载 `harness.toml`、`app.add_tools(all_tools())` 注册应用层工具、`app.cli()`。原 Composition Root 逻辑整体迁入 `harness/app/assembly.py` |
| `app_tools` | P2·P5·P9·**P13** | **应用层工具包**：所有工具都在这里定义并按 `calculator.py` 的统一格式导出 `tool_list`（`__init__.py` 汇总为 `all_tools()`）——计算器、`create_note` 副作用工具、工作区工具 `workspace_list` / `read` / `write` / `command` / `knowledge_search`；框架层不 import 本包 |
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
| 11 | Commercial Platform | 已完成 | Tenant / Plan / API Key 认证与 Principal、Usage Ledger 与 Reconciler、Billing Preview、Admin Control Plane API、FastAPI HTTP Surface + Lifespan 托管 Worker（Quota 于 0.13 降为兼容门面） |
| 12 | Open-Source DX & Backend Redesign | 已完成 | `HarnessApp` 门面、函数式 Tool 注册、声明式 `harness.toml`、Entry Point 插件、可选依赖 Extras、Local-first Server、`harness.app` 内部组合根 |
| 13 | Streaming Workbench & App-Layer Tools | 已完成 | 真实流式模型输出、`RunEventBroker` + SSE、工作区 / 会话 / 知识库的本地端点、业务工具下沉到 `app_tools/`、前端收敛为「工作区 + 对话」、个人运行不再受配额与调用预算限制 |

## 快速开始

### 环境要求

- Python 3.11+（`[rag]` / `[mcp]` 两条 Extra 实际需要 3.12+，因为 `chromadb>=1.0` 与 `mcp>=2` 的 Python 下限；CI 跑 3.12 与 3.13）
- Core 依赖由 `pyproject.toml` 声明：`openai`、`pydantic>=2`、`python-dotenv`、`jsonschema`、`opentelemetry-api`
- 其余按需安装：`[rag]` → `chromadb`，`[mcp]` → `mcp[cli]`，`[observability]` → OTel SDK 与 OTLP Exporter，`[server]` → `fastapi` / `uvicorn`（开发另需 `pytest`、`pytest-asyncio`、`httpx`、`ruff`、`mypy`、`build`）

### 安装

```bash
# 只装内核（零配置即可跑 Chat / Doctor / Check）
pip install -e .

# 常用组合：本地 HTTP Server + 开发工具
pip install -e ".[server,dev]"

# 需要 RAG / MCP / 可观测性时
pip install -e ".[rag,mcp,observability]"

# 全部可选组件
pip install -e ".[all]"
```

### 30 秒上手

```python
# example.py
from harness import HarnessApp

app = HarnessApp()          # 零配置；没有 harness.toml 也能启动


@app.tool
def add(a: float, b: float) -> float:
    """计算两个数字的加法。"""
    return a + b


if __name__ == "__main__":
    app.cli()               # 默认进入 Durable Chat
```

```bash
export DEEPSEEK_API_KEY=...    # 默认 Provider 是 DeepSeek
export DEEPSEEK_MODEL=deepseek-chat
python example.py
```

**不需要**先理解 `Registry` / `Store` / `Manager` / `UnitOfWork` / `DurableWorker`，也不需要手工组装任何组件。装饰器**保留原函数**：`add(1, 2)` 仍然是普通的 Python 调用，因此 Tool 可以直接单元测试。

### 工具放在哪、在哪注册

工具**全部定义在应用层的 `app_tools/`**，框架层（`harness/`）不内置任何业务工具，也**不 import `app_tools`**——那个包不随发行版安装，反向依赖会让 `pip install mini-harness` 之后构建运行时必然 `ModuleNotFoundError`。

```bash
python main.py serve      # 入口：注册 app_tools 里的全部工具
```

`main.py` 只有一行注册：

```python
from app_tools import all_tools
app.add_tools(all_tools())
```

每个工具模块按同一格式编写（对齐 `app_tools/calculator.py`）：**Pydantic 入参模型 → 普通函数 → `tool_from_pydantic(...)` → 模块底部导出 `tool_list`**。

```
app_tools/
├─ __init__.py    all_tools()：汇总所有无运行时依赖的工具
├─ calculator.py  add / subtract / multiply / divide
├─ notes.py       create_note（副作用 + 审批）
├─ workspace.py   workspace_list / read / write / command / knowledge_search
└─ knowledge.py   search_knowledge_base（需要检索管线，由组合根按 [rag] 单独注册）
```

工作区工具从 `ToolContext.workspace_path` / `knowledge_path` 取沙箱目录（服务端在提交 Run 时解析一次），因此它们不依赖数据库或服务对象，可以用普通单元测试直接覆盖。加一个工具的完整写法：

```python
# app_tools/workspace.py 里追加，格式与其它工具完全一致
class WorkspaceGrepArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pattern: str = Field(min_length=1)

def workspace_grep(pattern: str, *, context: ToolContext) -> dict:
    root = _workspace_root(context)
    return {"matches": [line for line in ...]}

workspace_grep_tool = tool_from_pydantic(
    name="workspace_grep",
    description="在工作区内按关键词搜索文件内容",
    args_model=WorkspaceGrepArgs,
    handler=workspace_grep,
    source="workspace",
    inject_context=True,          # handler 会收到 context=ToolContext
)
tool_list = [..., workspace_grep_tool]      # 加进模块的 tool_list 即完成注册
```

`requires_approval=True` / `side_effect=True` 决定这次调用是否需要人工批准（前端会自动出现批准 / 拒绝按钮，无需改前端）；`timeout_seconds`、`max_retries`、`required_permissions` 同理。

安装为包之后，命令行入口同样可用：

```bash
mini-harness --config harness.toml doctor
```

> CLI 会先把当前目录与配置文件所在目录补进 `sys.path`，因此 `mini-harness serve` 也能 import 项目自己的 `app_tools`；如果工厂模块存在但内部 import 失败，会直接抛出真实异常，而不是静默退化成「一个工具都没有」。

## 声明式配置 harness.toml

`harness.toml` 是**可选**的：没有它就走零配置。`load_config()` 会把缺失文件视为「全部用默认值」，并支持 `${VAR}` / `${VAR:-default}` 环境变量展开。

```toml
[app]
name = "mini-harness-demo"
provider = "deepseek"          # 默认；可显式改为 "openai"
database_path = "data/harness.db"
max_steps = 8

[security]
enabled = true
approval_required_for_side_effects = true

[durable]
enabled = true
worker_count = 2

[observability]
enabled = false                # 需要 [observability] Extra

[rag]
enabled = false                # 需要 [rag] Extra；Embedding 走 Qwen

[mcp]
enabled = false
servers = []

[plugins]
auto_discover = false           # 默认显式 app.use(plugin)，避免无意执行第三方代码
names = []

[server]
enabled = false
mode = "local"                  # local | platform
host = "127.0.0.1"
port = 8008
allow_unsafe_public_no_auth = false

[platform]
enabled = false                 # Phase 11 作为可选扩展
```

配置与代码的分工：**能声明的事实放 TOML，需要逻辑的注册放代码**。`HarnessApp.from_toml("harness.toml", optional=True)` 读取配置，`app.add_tools(all_tools())` 负责注册——工具定义在 `app_tools/`，框架不内置业务工具。

## 可选组件与 Extras

`Missing Extra` 不会变成裸 `ImportError`：所有可选依赖都走 Lazy Import，缺失时抛出 `FeatureDependencyError`，错误信息里直接给出可执行的安装命令。

| Extra | 启用配置 | 缺依赖时的提示 |
| --- | --- | --- |
| `rag` | `[rag].enabled = true` | `pip install "mini-harness[rag]"` |
| `mcp` | `[mcp].enabled = true` | `pip install "mini-harness[mcp]"` |
| `observability` | `[observability].enabled = true` | `pip install "mini-harness[observability]"` |
| `server` | `[server].enabled = true` 或 `serve` 子命令 | `pip install "mini-harness[server]"` |
| `platform` | `[platform].enabled = true` | `pip install "mini-harness[server]"` |

关闭全部可选组件时，`Observability` / `Metrics` / `Security` 会退化为 Noop 实现，内部调用接口保持稳定，因此内核永远不需要 `if enabled:` 分支。

## 开发者 CLI

```bash
mini-harness --help
```

| 子命令 | 说明 |
| --- | --- |
| `chat` | 本地 Chat，默认 Durable Mode（`--immediate` 切到 Immediate Mode） |
| `serve` | 启动 HTTP API（`--host` / `--port` 覆盖配置） |
| `doctor` | 检查配置与可选依赖，**不调用模型** |
| `plugins` | 列出已安装的 `mini_harness.plugins` Entry Point |
| `security-check` | 验证 Phase 9 Security（审批 / 注入信号 / 脱敏 / 进程隔离） |
| `durable-check` | 验证 Phase 10 Durable Execution（WAITING → 审批 → COMPLETED） |
| `eval` | 运行 Phase 8 评测数据集并写出报告 |
| `platform-init` | 初始化可选 Phase 11 Platform Extension 并发行 API Key |

`doctor` 会按当前 Provider 检查对应环境变量（默认检查 `DEEPSEEK_MODEL` / `DEEPSEEK_API_KEY`；`provider = "openai"` 时检查 `OPENAI_*`），并在启用 RAG 时额外要求 `DASHSCOPE_API_KEY`（Embedding 走 Qwen）。任一项 FAIL 时以退出码 2 结束。

## 本地 HTTP Server

```bash
pip install -e ".[server]"
mini-harness serve --port 8008
```

| 端点 | 说明 |
| --- | --- |
| `GET /healthz` | 健康检查（含版本与 `mode`） |
| `POST /v1/runs` | 提交 Run（202，由 Worker 异步推进） |
| `GET /v1/runs/{run_id}` | 查询 Run |
| `POST /v1/runs/{run_id}/approve` · `/cancel` | 审批与取消 |

**Local 模式没有 Authentication，因此只允许绑定 loopback。** 绑定 `0.0.0.0` 会被拒绝（`UnsafeServerConfigurationError`），除非显式设置 `server.allow_unsafe_public_no_auth = true`。公网多租户部署应改用 `server.mode = "platform"`（Phase 11 Platform Extension）或在前置网关做认证。

## 插件

第三方包通过 PyPA Entry Points 暴露插件，组名 `mini_harness.plugins`；插件只需要一个 `register(app)` 方法：

```python
class GreetingPlugin:
    name = "greeting"

    def register(self, app: HarnessApp) -> None:
        @app.tool
        def greet(name: str) -> str:
            """向指定名字打招呼。"""
            return f"你好，{name}！"


app = HarnessApp()
app.use(GreetingPlugin())      # 显式注册（推荐）
```

**默认不自动发现。** 只有明确设置 `[plugins].auto_discover = true` 才会扫描并执行已安装第三方包的代码，这是有意的安全取舍：安装一个包不应该等于执行它。

## 环境变量

**0.12 起配置的唯一来源是 `harness.toml`。** 直接读取环境变量的只有下面这几项——它们要么是凭据（不该写进 TOML），要么必须在启动最早期确定：

```env
# 对话模型(DeepSeek)：默认 Provider
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 显式切换 OpenAI Provider（harness.toml 里 provider = "openai"）时才需要
OPENAI_MODEL=
OPENAI_API_KEY=

# 向量模型(阿里云 DashScope)：Embedding 固定走这里，不读 OPENAI_API_KEY
DASHSCOPE_API_KEY=sk-xxxx
DASHSCOPE_MODEL=text-embedding-v3
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 商业平台(Phase 11)：Pepper 必须稳定保存，不能每次启动随机变化，
# 否则已发行的 API Key 全部失效。
HARNESS_API_KEY_PEPPER=

# 覆盖 CLI 默认加载的工厂模块（默认 main:app）
HARNESS_APP=main:app
```

`harness/__init__.py` 会加载项目根目录的 `.env`（**不覆盖**已存在的真实环境变量），因此上面这些凭据写在 `.env` 里即可。

**其余设置一律来自 `harness.toml`**：数据库路径、Worker 数量与租约、上下文预算、Guard 阈值、禁用工具、审计路径、可观测性导出与日志级别、平台计量参数等。需要让某个值随环境变化时，请在 TOML 里用 `${VAR}` / `${VAR:-default}` 展开，而不是指望子模块去读环境变量：

```toml
[app]
database_path = "${HARNESS_DATABASE_PATH:-data/harness.db}"

[durable]
worker_count = 2

[security]
max_input_chars = 16000
disabled_tools = []          # 逗号分隔的清单在这里写成 TOML 数组

[observability]
log_level = "${LOG_LEVEL:-INFO}"
```

> 升级提示：0.12 之前直接生效的 `HARNESS_DATABASE_PATH` / `HARNESS_WORKER_COUNT` / `OTEL_MODE` / `MAX_CONTEXT_TOKENS` / `HARNESS_DISABLED_TOOLS` 等变量**现在只在你把它们写进 TOML 时才生效**；`HARNESS_MAX_TOOL_CALLS_PER_RUN` 已彻底不再被读取（0.13 起调用预算不再拦截运行）。完整对照见 [docs/migration-v0.12-to-v0.13.md](docs/migration-v0.12-to-v0.13.md)。

> MCP 演示服务器未启动时不影响启动：`required=False` 的可选服务器发现失败会自动降级。

### 模型与向量 Provider（同构可替换）

项目里**每一处 OpenAI 模型调用都有一个同构的 DeepSeek 实现**，并且实际调用点全部走 DeepSeek / Qwen（参数直接取 `.env` 中已有的 `DEEPSEEK_*` / `DASHSCOPE_*`）。OpenAI 实现被完整保留，可通过显式参数切回：

| 能力 | 默认（实际调用） | 保留的 OpenAI 实现 | 调用点 |
| --- | --- | --- | --- |
| 对话模型 | `DeepSeekProvider`（chat 接口，零参构造读 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL`） | `OpenAIProvider`（Responses 接口） | `harness/app/assembly.py` `assemble_runtime()` |
| LLM Judge | `DeepSeekJudgeEvaluator`（chat 接口 + `json_object` 输出） | `OpenAIJudgeEvaluator`（Responses 接口 + 严格 `json_schema`） | `mini-harness eval --judge-model` |
| 向量模型 | `QwenEmbeddingProvider`（DashScope OpenAI 兼容模式，读 `DASHSCOPE_*`） | `OpenAIEmbeddingProvider` | `harness/app/assembly.py` `assemble_runtime()`（`[rag].enabled = true`） |

三者都遵循同一协议（`generate` / `evaluate` / `embed_documents` + `embed_query`），构造参数已对齐（`model` / `api_key` / `base_url` / `batch_size`），因此可以零参构造后直接互换，不需要改动 Runner、Retriever 或 Evaluator。两个 Judge 还共用同一套 Prompt 与评分契约（`score` 0–1 + `reason`），判定口径一致。

> **注意**：`OpenAIProvider` / `OpenAIJudgeEvaluator` / `OpenAIEmbeddingProvider` 需要 `OPENAI_API_KEY` 才能构造；本仓库默认不配置它，因此这三条路径不会在缺省运行中被触发。

### 运行入口

Phase 12 起 `main.py` 只有 13 行，**所有子命令都收敛到 `harness/cli.py`**，由 `mini-harness` 命令统一提供。`python main.py <子命令>` 与 `mini-harness <子命令>` 完全等价（前者通过 `app.cli()` 进入同一个解析器）。

| 子命令 | 说明 |
| --- | --- |
| `mini-harness chat` | 本地 Chat，**默认 Durable Mode**（不带子命令时的默认动作） |
| `mini-harness chat --immediate` | 切到 Immediate Mode（Phase 1–9 的 `chat` 行为） |
| `mini-harness serve` | 启动 HTTP API，`--host` / `--port` 覆盖配置 |
| `mini-harness doctor` | 检查配置与可选依赖，**不调用模型**；失败时退出码 2 |
| `mini-harness plugins` | 列出已安装的 `mini_harness.plugins` Entry Point |
| `mini-harness durable-check` | Phase 10 验收（Scripted Model，不需要 API Key） |
| `mini-harness security-check` | Phase 9 验收（审批 / 脱敏 / 注入信号 / 进程隔离） |
| `mini-harness eval` | Phase 8 Evaluation Suite |
| `mini-harness platform-init` | 初始化可选 Phase 11 Platform Extension 并发行 API Key |

`--config` 是全局参数，默认 `harness.toml`：

```bash
mini-harness --config harness.toml serve
python main.py --config harness.toml serve
```

组装流程由 `harness/app/assembly.py` 的 `assemble_runtime()` 完成：可观测性（或 Noop）→ SQLite（WAL + Phase 1–9 Schema + Durable Schema）→ Durable Store / Approval / Budget / Idempotency → Security → 工具注册（项目工具 / 内置 RAG / MCP）→ `ContextBuilder` → Model Provider（默认 DeepSeek）→ `ToolExecutor` → `AgentRunner` → Immediate 与 Durable 两条应用路径。会话、运行状态与消息都会持久化，多轮输入续接同一会话。

两条不需要 API Key 的验收命令：

```bash
# 预期：第一次执行 WAITING → 审批后 COMPLETED
mini-harness durable-check

# 预期：未审批 APPROVAL_REQUIRED → 审批后 SUCCESS
mini-harness security-check

# 预期：全部 [OK]（配置与可选依赖自检，不调用模型）
mini-harness doctor
```

> **从 0.11 迁移**：`python main.py api` → `mini-harness serve`，`durable-chat` → `chat`，`chat` → `chat --immediate`，`platform-check` → `mini-harness doctor`。详见 [docs/migration-v0.11-to-v0.12.md](docs/migration-v0.11-to-v0.12.md)。
>
> **从 0.12 迁移**：环境变量收敛进 `harness.toml`、配额与调用预算不再拦截运行。详见 [docs/migration-v0.12-to-v0.13.md](docs/migration-v0.12-to-v0.13.md)。

### 商业平台（Phase 11 可选扩展）

Platform 默认关闭。启用前先设置一个**稳定**的 Pepper，再初始化并启动：

```powershell
# Pepper 必须长期保存；每次启动随机变化会让已发行的 API Key 全部失效。
$env:HARNESS_API_KEY_PEPPER = "请换成你自己的高熵长期 Secret"

# 创建套餐（starter_v1 / pro_v1 / operator_v1）、租户（_platform / tenant_demo）并发行 API Key。
# 明文 API Key 只打印这一次，请立即保存到 Secret Manager。
mini-harness platform-init
```

然后打开 Platform 模式（`harness.toml`）：

```toml
[server]
mode = "platform"          # 默认 local

[platform]
enabled = true             # 默认 false；需要 [server] Extra
```

```bash
mini-harness serve         # 默认 http://127.0.0.1:8008
```

启动后工作台在 `http://127.0.0.1:8008/`，OpenAPI UI 在 `http://127.0.0.1:8008/docs`。

### 对话工作台

工作台只有两件事：**创建工作区** 与 **在工作区里对话**。前端为 **Vue 3 + TypeScript + Vite + Pinia**，构建产物已入库，因此运行时不需要 Node.js，静态资源由 FastAPI 同源提供：

```bash
# Local 模式：无需 API Key，无认证，仅监听 loopback
mini-harness serve
# 打开 http://127.0.0.1:8008/
```

- **工作区**：输入目录路径，或从服务端目录列表里逐级点选；目录不存在时可勾选创建。工作区绑定一个本地目录，Agent 的文件读写与命令执行都限制在它内部，路径越界会被拒绝。
- **流式对话**：提交任务后前端订阅 `GET /v1/runs/{run_id}/stream`，模型文本按增量逐字显示，并以 Markdown 渲染（标题、列表、表格、代码块、引用）。`marked` 的输出经 `DOMPurify` 消毒后才注入，模型输出始终按不可信内容处理。
- **工具调用可见**：每次调用是一张卡片——工具名、参数、状态（执行中 / 等待批准 / 完成 / 失败 / 已跳过）；点击展开可看完整返回内容，`workspace_write` 直接给出修改前后的 diff。
- **人在回路**：`workspace_write` 与 `workspace_command` 需要批准。运行停在等待状态时，对话里出现批准 / 拒绝按钮；批准后**同一条事件流继续**输出，不需要刷新页面。
- **会话与历史**：一个工作区可以有多个会话。切换会话时按 `conversation_id` 拉取历史 Run，用与实时流相同的结构重建对话（用户指令 → 工具调用 → 最终答案）。会话在发送第一条指令时自动命名（不再是清一色的「新任务」），侧栏提供 **归档 / 恢复** 与 **删除**；删除会二次确认，并连带清理该会话的 Run、步骤、检查点与消息，正在执行中的会话会被拒绝删除（409）。
- **断线不重跑**：事件总线为每次 Run 保留回放缓冲（最近 32 次），页面刷新或另开客户端重新连接时先整体回放、再续播实时事件，因此既不会丢内容也不会重复执行。重连后的重放帧按事件序号去重；万一事件流完全不可用（旧服务、代理缓冲、长断线），前端会自动降级为轮询同步并在界面上说明，文本与工具调用仍会收敛到服务端真相。

> `python -m harness.ui` 只是静态预览：它仅提供文件服务，没有 API 与 Worker，因此没有工作区与对话能力。

> **工作台面向 Local 模式**（`server.mode = "local"`）。工作区 / 会话 / 事件流都是本地端点；Platform 模式（多租户 + API Key）继续提供 Phase 11 的 Run API，但不会挂载工作区端点，此时工作台只提供静态外壳。

### 前端源码与构建

源码在 `frontend/`，构建产物输出到 `harness/ui/static/`（**入库**，请勿手改）：

```bash
cd frontend
npm install          # 依赖：vue / pinia / marked / dompurify / vite / typescript / vue-tsc / vitest
npm run dev          # 开发模式，/healthz 与 /v1 代理到 127.0.0.1:8008
npm run build        # vue-tsc 类型检查 + vite build（产物为 harness/ui/static）
npm run test         # vitest + jsdom：流式增量归并、Markdown 渲染与消毒、工具卡片、审批
```

```
frontend/src/
├─ App.vue       工作区侧栏 + 对话主区（含批准 / 拒绝 / 停止）
├─ components/   MarkdownText（marked + DOMPurify）· ToolCallCard（参数/状态/输出/diff）· WorkspaceCreator
├─ stores/       chat（工作区 / 会话 / 轮次 / SSE 事件归并）
├─ api/          client（唯一 fetch 出口 + EventSource 流）· storage（localStorage 容错端口）
└─ styles/       app.css（单文件主题与全部样式）
```

独立预览只绑定本机回环地址；需要真实模型执行时，请使用完整 API 服务地址。

### API 端点

**两种模式暴露的端点不同**，由 `[server].mode` 决定。

Local 模式（`mode = "local"`，默认）——**无认证、无 Scope**，只允许 loopback：

| 端点 | 说明 |
| --- | --- |
| `GET /healthz` | 健康检查，返回 `{status, version, mode: "local"}` |
| `POST /v1/runs` | 提交 Run（202，由 Durable Worker 异步推进） |
| `GET /v1/runs` · `GET /v1/runs/{run_id}/trace` | Run 列表（可带 `conversation_id` 过滤）与观测视图（步骤 / 工具 / 用量） |
| **`GET /v1/runs/{run_id}/stream`** | **SSE 事件流**：`run.submitted` / `model.start` / `model.delta` / `model.end` / `tool.start` / `tool.end` / `phase` / `run.waiting` / `run.end`，先回放缓冲再续播实时事件 |
| `POST /v1/runs/{run_id}/approve` · `/reject` · `/cancel` | 审批、拒绝与取消（202） |
| `POST /v1/runs/{run_id}/pause` · `/resume` · `/instructions` · `/replay` | 暂停、继续、附加指令与从检查点重跑 |
| `GET /v1/workspaces` · `POST /v1/workspaces` | 工作区列表与新增（绑定本地目录） |
| `GET /v1/directories` | 目录浏览：只返回子目录名，不返回文件内容 |
| `GET /v1/sessions` · `POST /v1/sessions` | 工作区下的会话（对话）列表与新建；`archived=true` 返回归档会话 |
| `PATCH /v1/sessions/{id}` · `DELETE /v1/sessions/{id}` | 会话重命名 / 归档 / 恢复，以及删除（含 Run、步骤、检查点与消息；执行中的会话返回 409） |
| `GET /v1/workspaces/{id}/files` · `/file` | 工作区内文件浏览与文本预览（限制在目录边界内） |
| `GET /v1/workspaces/{id}/knowledge` · `/knowledge/upload` · `/knowledge/import` | 工作区知识库：列表、上传与从本地文件导入 |
| `GET /` · `/ui/*` | 对话工作台（`/` 返回 index.html，`/ui` 提供静态资源） |

Platform 模式（`mode = "platform"`）——**需要 `X-API-Key` 与 Scope**：

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
| `GET /` · `/ui/*` | 无 | 工作台静态外壳（工作区与对话端点是 Local 模式专有） |

**关键约束**：Tenant、Plan、Tool Permission 都由服务端从 API Key 与数据库解析（`Principal` → `Tenant.plan_id` → `Plan.tool_permissions`），**客户端不能提交 `tenant_id` 或 `permissions`**——否则等于让调用方自己给自己发权限。（0.13 起 Quota 只记账不拦截，因此它不再是「服务端事实」链路上的一环。）

无模型的平台冒烟：

```bash
# 覆盖 Platform Schema / API Key 发行与认证 / Tenant / Plan / Usage / Billing Preview
# 以及「配额只记账不拦截」的新语义（0.13）
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
Plan ──► QuotaService（0.13 起为兼容门面：恒 UNLIMITED，只记账不拒绝）
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

```
mini-harness/
├── main.py                    # 项目入口（13 行）：加载 harness.toml、注册工具、app.cli()
├── harness.toml                # 声明式配置（可选；缺失即零配置启动）
├── example.py                 # 最小示例（可删除）
├── pyproject.toml             # 元数据、Core 依赖、Extras、console_scripts、pytest / ruff / mypy
├── .env.example               # 仅列出真正被直接读取的环境变量（凭据 + Pepper；`.env` 被 .gitignore 排除）
├── SECURITY.md / CONTRIBUTING.md / CHANGELOG.md / LICENSE
├── .github/workflows/ci.yml   # Install → Compile → Test → Build
├── docs/
│   ├── architecture.md        # 开发者层与内部执行层边界、Public vs Internal API
│   ├── migration-v0.11-to-v0.12.md
│   ├── migration-v0.12-to-v0.13.md  # 环境变量收敛、配额与调用预算变化
│   └── plugins.md             # 插件契约与 Entry Point 规范
├── examples/                  # quickstart.py / plugin_example.py
├── harness/
│   ├── __init__.py            # 公共 API：HarnessApp / HarnessConfig / HarnessPlugin / tool / Tool / ToolContext
│   ├── cli.py                 # P12：mini-harness 命令行
│   ├── streaming.py           # P13：RunEventBroker（SSE 事件总线 + 回放缓冲）
│   ├── app/                   # P12：开发者门面层与内部组合根
│   │   ├── application.py     #   HarnessApp（门面）
│   │   ├── config.py          #   HarnessConfig + load_config（TOML + ${VAR} 展开，配置的唯一来源）
│   │   ├── assembly.py        #   内部 Composition Root（所有 Store / Service / Worker 组装在这里）
│   │   ├── tooling.py         #   to_tool / @tool（typed callable → Tool，保留原函数）
│   │   ├── plugins.py         #   Entry Point 插件发现
│   │   ├── features.py        #   内置 RAG Tool
│   │   ├── server.py          #   Local HTTP API + loopback 保护
│   │   ├── desktop.py         #   P13：工作区 / 会话 / 知识库 / 控制的服务层
│   │   ├── desktop_api.py     #   P13：工作区、会话与事件流路由（仅 Local 模式）
│   │   ├── checks.py          #   security-check / durable-check
│   │   ├── runtime.py         #   RuntimeBundle（高级逃生口）
│   │   ├── noop.py            #   Noop Observability / Metrics / Security
│   │   └── errors.py          #   FeatureDependencyError / UnsafeServerConfigurationError
│   ├── models.py              # ToolCall / ModelUsage / ModelResult / RunResult / RunEvidence
│   ├── runner.py              # AgentRunner：run() 即时循环 + create_execution()/advance() 分段推进
│   ├── application.py         # PersistentAgentService：多轮会话 + 持久化编排 + RunEvidence 回传
│   ├── tools/                 # 工具运行时（定义 / 工厂 / 校验 / 注册 / 中间件 / 幂等 / 执行 / 结果）
│   ├── context/               # 上下文工程（Token 预算 + ContextPolicy + sources + 历史裁剪）
│   ├── state/                 # 状态模型（Conversation/Run/Step/Checkpoint/RuntimeEvent）
│   ├── persistence/           # 完整 SQLite Schema（含 Durable 表）+ 仓储 + UnitOfWork
│   ├── providers/             # DeepSeek（chat，默认，流式）/ OpenAI（responses，可切换）适配
│   ├── retrieval/             # RAG：加载 / 切分 / 嵌入（Qwen 默认·OpenAI 保留）/ 向量存储 / 检索 / 投影
│   ├── mcp/                   # MCP：配置 / 完整网关 / 发现 / 适配 / 资源
│   ├── observability/         # 可观测性：引导 / span / 指标 / 日志 / 成本 + Collector 参考配置
│   ├── evaluation/            # Phase 8：数据集 / 评估器 / Judge / 运行器 / 报告与质量门
│   ├── security/              # Phase 9：Guard / ToolPolicy / Approval / Audit / Sandbox
│   ├── durable/               # Phase 10：配置 / 模型 / 序列化 / Trace / Store / Service / Worker
│   ├── platform/              # Phase 11（可选扩展）：配置 / Schema / Store / Auth / Quota（兼容门面）/ Metering / Billing / API
│   └── ui/ + frontend/        # P11·P13 对话工作台（后端托管 + Vue 3 源码）
├── app_tools/                 # 应用层工具包：calculator / notes / workspace / knowledge（框架层不 import）
├── mcp_servers/               # 演示 MCP Server
├── evals/                     # 评测数据集（datasets/）与报告（reports/）
├── scripts/                   # 演示与诊断脚本（含 security_smoke_test）
├── tests/                     # pytest 测试（app_tools / desktop_api / run_stream / public_app / app_config_plugins …）
└── del/                       # 归档：旧版实现、已废弃模块与历史测试（不入库）
```

> 各子系统通过 `harness` 内部接口解耦，新增模块不影响已有代码。

## 设计要点

- **内部复杂，外部简单**：`HarnessApp` 是唯一需要理解的入口；`Registry` / `Store` / `Manager` / `UnitOfWork` / `DurableWorker` 全部收敛进 `harness/app/assembly.py`，但**一个都没有删除**，高级开发者仍可通过 `app.runtime` 取到原始组件做精细控制
- **Public API 与 Internal API 分层**：`harness/__init__.py` 只导出 7 个稳定符号；其余路径视为内部实现，升级时可能变动（见 `docs/architecture.md`）
- **Tool 注册是函数式的**：`@app.tool` 声明能力但**返回原函数**，因此 Tool 逻辑可以脱离 Harness 直接单元测试；普通带类型注解的 `callable` 也能直接 `app.add_tool()`，旧 `Tool` 对象与 `tool_list` 继续兼容
- **Build 之后不可变**：`app.build()` 一旦执行，再注册 Tool / Plugin 会抛 `RuntimeError`。有意如此——运行中的注册表变化会让「这次运行用了哪些工具」不可复现
- **可选依赖靠 Lazy Import 成立**：Core 只依赖 `openai` / `pydantic` / `python-dotenv` / `jsonschema` / `otel-api`，RAG / MCP / Observability / Server 都在真正启用时才导入，缺失时抛 `FeatureDependencyError` 并给出安装命令
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
- **事件流只是「加速观看」，服务端视图才是事实**：`RunEventBroker` 连接时先整体回放缓冲、再续播实时事件，因此迟到订阅者不丢内容也不重复；前端在事件流完全不可用时自动降级为每 2 秒轮询对账，界面同时说明当前处于轮询同步
- **业务工具属于应用层**：框架层（`harness/`）不定义、也不 import 任何业务工具；工作区目录通过 `ToolContext.workspace_path` / `knowledge_path` 注入，工具因此不依赖数据库或服务实例，可以用普通单元测试覆盖，也不会在 `pip install mini-harness` 之后因缺 `app_tools` 而构建失败
- **本地优先的配额取舍**：面向个人的运行不设配额与调用预算——`QuotaService` 保留接口形状但恒返回 `UNLIMITED`，调用预算门面恒返回 `True`，用量照常进入账本。真正需要收费或限流的部署应在网关或 Platform 扩展里做，而不是让本地 Agent 因为缺少套餐配置而无法启动
- **Provider 同构替换**：模型（`DeepSeekProvider` ↔ `OpenAIProvider`）、Judge（`DeepSeekJudgeEvaluator` ↔ `OpenAIJudgeEvaluator`）、向量（`QwenEmbeddingProvider` ↔ `OpenAIEmbeddingProvider`）三对实现共享同一协议与同一套构造参数，默认使用 DeepSeek / Qwen，OpenAI 实现完整保留；替换 Provider 不需要改动 Runner、Retriever、Evaluator 任何一行

## 开发状态

项目已按 13 个阶段完成主体建设（v0.13.0），接口与目录结构仍可能随维护调整。各阶段完成后会同步更新本文档的路线图与能力清单（详见 [CHANGELOG.md](CHANGELOG.md)）。

- **后端测试**：`pytest -q`（当前 56 项）覆盖可观测性 / 评估 / 安全 / 持久执行 / 沙箱 / 商业平台，以及公开 API 与配置（`test_public_app` / `test_app_config_plugins`）、应用层工具（`test_app_tools`）、桌面 API 与事件流（`test_desktop_api` / `test_run_stream`）；历史测试位于 `del/tests/` 归档
- **前端测试与构建**：`cd frontend && npm run test`（vitest + jsdom）覆盖流式增量归并、Markdown 渲染与消毒、工具卡片与审批；`npm run build` 依次执行 `vue-tsc --noEmit` 与 `vite build`，产物写入 `harness/ui/static/`（构建产物入库，运行时不需要 Node.js）
- 在无法创建临时目录的受限环境（部分容器 / 沙箱）中，依赖私有临时目录的步骤会报 `PermissionError`：pytest 的 `tmp_path`、以及 `security-check` / `ProcessIsolationSandbox` 的 `TemporaryDirectory` 都属于这一类。这属于环境限制而非代码缺陷——换到普通 shell 或放宽目录权限即可通过
- **SQLite 的真实商业边界**：`Durable Store` 与 `Platform Store` 目前共用同一个 SQLite 文件，WAL 依赖同主机共享内存，因此只适用于**本地优先产品 / 单节点 SaaS MVP / 小团队内部服务 / 教学与 Preview Release**；不应声称支持多 Region、多节点 HA 或百万 QPS Control Plane。真正规模化应把 `PlatformStore`、`DurableStore`、`Usage Ledger` 迁移到 PostgreSQL，并把 HTTP Rate Limit 放到 Gateway / Redis
- **当前明确遗留**：① 既没有分布式 HTTP Rate Limiter，也没有服务端强制的用量上限——0.13 起配额与调用预算只计量不拦截，需要限流请在网关层实现；② Usage Ledger 与 Durable Submit 之间不是跨领域原子事务（靠稳定 `event_key` + 对账解决重复，支付级系统应上 Transactional Outbox）；③ Billing 只是 Preview / 内部账本计算，尚无 Tax / Invoice Finalization / Refund / Credit Note / Payment Collection / Stripe Webhook；④ API Key 是第一版 M2M Auth，尚无 OAuth2 / 用户级会话；⑤ Admin Control Plane API 已完成，但没有品牌化 Dashboard UI（开发期用 `/docs`）；⑥ 工作台是单机 Local 形态，多用户协作需要自行叠加认证与部署层
- `.env`、`data/` 与 `del/` 已加入 `.gitignore`，不会提交到仓库；仓库只提供不含密钥的 `.env.example`。评测报告中的 `evals/reports/latest.json` 为每次运行产物，同样不入库（`baseline.json` 作为回归基线入库）
- API Key 明文**只在 `platform-init` 打印一次**，数据库只保存 HMAC 摘要；`HARNESS_API_KEY_PEPPER` 必须长期稳定保存，否则已发行的 Key 全部失效

## 贡献

欢迎参与共建！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发环境、提交规范与 PR 流程。

## 更新日志

版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
