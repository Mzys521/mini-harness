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


## Local workbench navigation

`frontend/src/App.vue` 保留同一个 Pinia 对话 Store 与聊天视图，普通/项目对话在辅助页面期间继续接收 SSE 并保留草稿。`useWorkbenchRoute.ts` 使用 Hash + History API 管理 `chat` / `temporary` / `pull-requests` / `automations` / `skills` / `preferences` / `plugins` / `explore`，不改变 FastAPI 静态托管入口，也不增加路由依赖。

`ProjectTree.vue` 将 Workspace 显示为项目文件夹，按工作区 ID 缓存活动/归档会话。新建图标位于展开箭头之前，共享行背景。`ChatList.vue` 在项目下方显示普通对话，使用空工作区缓存键；普通会话元数据单独存入 `desktop_chats`，共享原 Conversation/Run 存储，旧工作区表和外键不变。点击链接校验会话归属，归档/删除显式携带目标工作区。

`CapabilityPage.vue` 展示 MCP、创建 RAG 仓库并上传 UTF-8 文件，RAG/MCP 关闭时显示服务提示。`PersonalPage.vue` 管理技能、使用习惯、定时任务；使用习惯作为 `AppearanceSettings.vue` 中的分类嵌入设置浮窗，侧栏不再独立列出。Pull Request 仍是说明页，不添加语音等无后端能力。

设置使用原生 dialog 管理模态焦点、Escape 和遮罩关闭，内部为左侧分类/右侧可滚动内容。appearance store 兼容原存储键，校验可选自定义颜色，派生主题 CSS 变量和按钮文字对比色；主题、字体和配色保存在浏览器，使用习惯仍通过原 Local API 保存。旧 `#/preferences` 路由转为打开设置分类，不切断当前临时对话。

对话正文与输入框限制为居中 880px。`ConversationLocator.vue` 仅消费现有 turns 与 transcript 元素，按轮次生成短横线和纯文本摘要，用被动 scroll 监听、requestAnimationFrame 和 ResizeObserver 跟随滚动与内容尺寸变化；卸载时清理监听。跳转事件通知 App 暂停自动跟随，不改变对话存储或 API。临时对话结束后，定位摘要随 turns 清空。

## Conversation usage metrics

`ModelResult.cache_usage_reported` 为可选布尔字段，默认 false；Provider 明确返回缓存计数时设为 true，避免缺失计数被误解成零命中。Runner 用单调时钟记录每次模型调用耗时，在 `model.end.metrics` 与已有 `transition_data.metrics` 放入输入/输出/总量、可空缓存计数、耗时和配置窗口；不增加领域依赖或数据库表。Desktop 将模型步骤的 metrics 透传，旧步骤缺失时保持缺失，临时运行只使用原有内存事件路径。

前端按模型步归并 metrics，SSE seq 防重复；历史回放和轮询恢复沿用同一投影。`ConversationMetrics.vue` 展示最近一轮统计和最近一次请求的上下文余量估算；显示开关保存在 appearance store，统计值不写入浏览器存储。精确请求计数及其边界见 [Token 计量规划](token-accounting-plan.md)。

## Local personal context and scheduling

`PersonalStore` 管理 `personal_preferences`、`personal_skills`、`personal_automations`，只负责 SQL；校验、时间与 ID 生成均在 `PersonalCatalog`。SKILL.md 的 name/description 描述性 frontmatter（含简单折行）与正文导入为个人指令，不解析任意 YAML 对象、不访问链接文件、不执行代码。用户在输入区选择启用技能，最多 8 个、合计 32000 字符。

`submit_local` 每次读取习惯、当前时间、技能、Agent 设置，提交给原 Durable 服务；项目对话附带当前知识库名称与 ID，让模型能检索前端新建的仓库。工作区对话保留工具快照机制，普通对话只开放需要审批的 `create_scheduled_task`、`remember_user_preference`。既有独立 SDK/API Conversation ID 继续由 Durable 做所属用户校验，工作区绑定校验由 Local 层处理。HTTP 端点仅挂载在 Local 模式。

`AutomationScheduler` 由唯一组合根装配，Local lifespan 与 Worker 同时启动。SQLite 条件更新 claim 下一次执行时间，随后建立项目/普通会话并提交 Durable。固定间隔按 UTC 计算，离线积压合并一次；先 claim 后提交意味着崩溃窗口可能漏一次，但不会擅自重放可能已提交的副作用。重启标记未完成提交为 interrupted；用户查明执行对话后重新安排。该功能没有操作系统唤醒/通知通道，服务关闭时不运行。

## Temporary chat non-retention

`TemporaryChats` 只持有内存会话（最多 100 个）、最近 20 条消息与单次 SSE 队列。组合根复用 `AgentRunner` 类、空工具注册表、Noop 观测；不修改 Runner，不调用 Durable、持久化 Store、全局 broker、安全审计写入或长期偏好工具。每次请求仍读取用户习惯与所选技能。

内置 Provider 的独立实例禁用留存：DeepSeek `_histories` 隔离且不写入；OpenAI Responses 请求 `store=false`。第三方 Provider 必须自行遵守相同无日志/无缓存契约，应用不能替服务商承诺零日志。消息请求只返回通用错误，不回传可能包含提示词的异常文本。

前端不将临时 ID/正文写入浏览器存储，结束/离开时清空草稿与消息；pagehide 使用 keepalive 结束请求。生成断开即取消并清除，未收到结束请求的闲置会话 30 分钟过期，每 30 秒清扫，单次生成最多 180 秒。临时消息 POST 使用 SSE 和 `Cache-Control: no-store`，不提供回放/重连历史。
