# 文件：docs/architecture.md
# Architecture

mini-harness 的核心设计约束是：**内部复杂，外部简单**。

## Developer-facing layer

普通开发者只需要接触这一层：

```text
harness/__init__.py          公共 API（7 个稳定符号）
harness/cli.py               命令行
harness/app/application.py   HarnessApp 门面
harness/app/config.py        HarnessConfig + load_config
harness/app/tooling.py       to_tool / @tool
harness/app/plugins.py       HarnessPlugin 协议
```

依赖方向是单向的：

```text
Developer
  ↓
HarnessApp
  ├── @app.tool / app.add_tool()
  ├── app.use(plugin)
  ├── harness.toml
  ├── app.chat() / app.ask() / app.submit()
  ├── app.create_http_app()
  └── app.runtime          ← 高级逃生口
```

## Internal execution layer

以下模块**全部保留**，但不再要求开发者手工组装：

```text
harness/app/assembly.py      ← 唯一的内部 Composition Root
harness/streaming.py         RunEventBroker（SSE 事件总线 + 回放缓冲）
harness/app/desktop.py       工作区 / 会话 / 知识库服务层（Local 模式）
harness/app/desktop_api.py   工作区、会话与事件流路由（Local 模式挂载）
harness/context/             Token 预算、ContextPolicy、ContextBuilder
harness/tools/               Tool 定义、工厂、校验、注册表、执行器、中间件、幂等
harness/persistence/         SQLite Schema、Repository、UnitOfWork
harness/durable/             DurableAgentService、Worker、Lease、Approval、Idempotency
harness/security/            Guard、ToolPolicy、Audit、Process Isolation
harness/retrieval/           RAG（可选）
harness/mcp/                 MCP 网关（可选）
harness/observability/       OTel（可选）
harness/evaluation/          评测
harness/platform/            Phase 11 商业平台（可选扩展；Quota 为兼容门面）
```

组件组装顺序（`assemble_runtime`）：

```text
Observability / Metrics（或 Noop）
  → Database + Durable / Approval / Budget / Idempotency Store
  → Security（或 NoopSecurityService）
  → ToolRegistry ← 注册 Tool、内置 RAG Tool、MCP 工具
  → ContextBuilder（TokenBudget + ApproxTokenCounter + ContextPolicy）
  → Model Provider（默认 DeepSeek；可注入替代实现）
  → ToolExecutor（Middleware + Security + Idempotency）
  → AgentRunner
  → PersistentAgentService（Immediate）与 DurableAgentService + DurableWorkerPool（Durable）
  → 可选：DesktopService（Local 工作台）与 RunEventBroker（事件流出口）
  → 可选：CommercialPlatformService
```

## Registration policy

### Normal project

```python
app = HarnessApp.from_toml("harness.toml")
app.add_tools(add_tool, create_note_tool)
```

Tool 注册在 `build()` 之前完成。`build()` 之后 `add_tool` / `add_plugins` 会抛 `RuntimeError`：

```text
Runtime 已经 build，不能再修改 Tool/Plugin；请在 build 前完成注册。
```

这不是限制，而是可复现性要求：一次运行用到哪些能力必须能在运行开始前确定。

### Third-party package

第三方包通过 PyPA Entry Points 声明插件，组名 `mini_harness.plugins`：

```toml
[project.entry-points."mini_harness.plugins"]
greeting = "my_package.plugin:GreetingPlugin"
```

默认**不自动发现**，必须 `app.use(plugin)` 或显式打开 `[plugins].auto_discover = true`。安装一个包不应该等于执行它的代码。

## Public vs internal API

| 稳定（Public） | 可能变动（Internal） |
| --- | --- |
| `HarnessApp` 及其方法 | `harness.app.assembly` 的一切 |
| `HarnessConfig` 与各 Settings 字段 | `harness.app.noop` / `runtime` |
| `tool` / `to_tool` | 各子系统 `*Store` / `*Manager` 的构造签名 |
| `HarnessPlugin` | `harness/cli.py` 内部函数 |
| `Tool` / `ToolContext` | |

`app.runtime` 返回的 `RuntimeBundle` 是**高级逃生口**：字段名稳定，但字段内的对象属于 Internal API。需要精细控制时使用它，同时接受升级成本。

## Optional dependency boundary

```text
Core（始终安装）      openai, pydantic, python-dotenv, jsonschema, opentelemetry-api
[rag]                chromadb
[mcp]                mcp[cli]
[observability]      opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http
[server]             fastapi, uvicorn
```

每条边界都通过 Lazy Import 实现：模块级只导入 Core，可选依赖在真正启用的分支里导入，`ImportError` 统一转成 `FeatureDependencyError`，附带可执行的安装命令。

关闭可选能力时，`NoopObservability` / `NoopMetrics` / `NoopSecurityService` 保持接口形状不变，因此内核代码里没有 `if enabled:` 分支。

## Configuration source of truth

**配置只有一个来源：`harness.toml`（经 `load_config()`）。** 子模块不读 `HARNESS_*` / `OTEL_*` / `MAX_*`；`HarnessConfig` 的每个字段都有默认值，因此没有 TOML 文件也能零配置启动。

```text
harness.toml ──(tomllib + ${VAR} 展开)──► HarnessConfig ──► assemble_runtime() ──► 各子系统
```

仍然直接读环境变量的只有三类，理由都是「不该或不能写进 TOML」：

| 变量 | 为什么仍然读环境 |
| --- | --- |
| `DEEPSEEK_*` / `OPENAI_*` / `DASHSCOPE_*` | 凭据，属于机器或 Secret Manager 而不是仓库 |
| `HARNESS_API_KEY_PEPPER` | 平台 HMAC Pepper，必须长期稳定且不入库 |
| `HARNESS_APP` | 决定加载哪个工厂模块，必须早于配置解析 |

需要让某个配置项随环境变化时，用 TOML 的 `${VAR}` / `${VAR:-default}` 展开，例如 `database_path = "${HARNESS_DATABASE_PATH:-data/harness.db}"`。

> 这条边界是 0.12 变更的，0.13 才把文档对齐：早期版本曾由各子系统自行 `os.getenv`，因此「直接设置环境变量就生效」的写法已经不再成立。
