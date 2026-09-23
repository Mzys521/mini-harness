# AGENT.md — mini-harness 架构与施工规范

> 本文件是给**后续 agent / 贡献者**的施工图。动手前先读：本文件 → `README.md` →
> `docs/architecture.md` → 当前阶段的 `HANDOFF.md`。三条冲突时的优先级：
> **本文件的硬性约束 > HANDOFF 的当前状态 > README 的描述**。
>
> 最后更新：2026-09-23（0.14.0 已发布：多 RAG 仓库、运行期 MCP、个人对话与调度）

---

## 1. 不可动摇的架构约束

### 1.1 Runner 是唯一的 Agent 主循环，且只是一个运行内核

`harness/runner.py` 的 `AgentRunner` 是**唯一**的「模型 → 工具 → 结果回传」循环实现。
它**不知道**任何其他模块的存在：不知道有工作台、不知道有 RAG 仓库、不知道有 MCP、
不知道有商业平台。

Runner 允许依赖的只有这些「内核契约」：

```
harness/context/models.py    WorkingState
harness/durable/models.py    AgentExecutionState / ExecutionPhase
harness/models.py            ToolCall / ModelResult / RunResult / RunEvidence
harness/streaming.py         accepts_keyword（签名探测）
harness/tools/result.py      ToolStatus
```

**禁止**在 Runner 里出现：`from harness.app...`、`harness.retrieval`、`harness.mcp`、
`harness.platform`、`harness.persistence`、`harness.security`，以及任何 `if <某功能> enabled`
的分支。新增能力要接进来，只能通过**已有的抽象**（`Tool` / `ToolRegistry` / `ToolExecutor` /
`ModelProvider` / emitter），而不是给 Runner 加依赖。

### 1.2 ToolRuntime 负责执行，Runner 不执行工具

工具的执行顺序、校验、权限、审批、幂等、超时、重试**全部**在
`harness/tools/executor.py::ToolExecutor` 里；Runner 只负责 `await self.executor.execute(...)`
并记录 `RunEvidence`。不要在 Runner 里内联任何执行细节。

### 1.3 Repository / Store 不含业务逻辑

数据访问层（`harness/persistence/**`、`*Store`）只做 SQL：

- 不生成 id、不读时钟、不做校验、不发起网络/文件操作
- 不 import 领域模块（`harness/retrieval`、`harness/mcp`、`harness/platform`）
- 业务编排放在各自的编排层：`harness/app/assembly.py`（组合）、
  `harness/retrieval/catalog.py`（RAG 仓库）、`harness/app/mcp_api.py` + `harness/mcp/manager.py`（MCP）

已核实的现状（改动后请保持）：`harness/persistence/*` 里**没有**任何
`knowledge_repositories` / `mcp_servers` 字样——可选能力的表由各自模块自建。

### 1.4 依赖方向：只能向下，禁止反向

```
harness/app/*        ← 组合根与传输层，可以 import 下面任何东西
      ↓
harness/cli.py       入口编排
      ↓
harness/retrieval · harness/mcp · harness/platform · harness/evaluation  可选能力
      ↓
harness/runner · harness/tools · harness/context · harness/durable · harness/security  内核
      ↓
harness/persistence · harness/state · harness/models · harness/streaming  基础设施与契约
```

规则：

| 禁止 | 原因 |
| --- | --- |
| 内核（runner/tools/context/durable/security）import `harness.app` / `harness.retrieval` / `harness.mcp` / `harness.platform` | 内核必须能在只装 Core 依赖时工作 |
| `harness.retrieval` / `harness.mcp` import `harness.app` / `harness.platform` | 可选能力不得反向依赖组合根 |
| `harness.persistence` import 任何领域模块 | 数据库层保持通用，否则关掉 RAG 也要建 RAG 的表 |
| 任何模块 import `app_tools` | `app_tools` 不在发行版 packages 里；框架 import 它会让 `pip install` 后必然 `ModuleNotFoundError` |

`harness/app/assembly.py` 是**唯一**的组合根：所有 Store / Service / Worker / Catalog 在这里组装，
其他地方不要自己拼运行时。

### 1.5 命名

- 动作前缀用：`register_xxx` / `get_xxx` / `create_xxx` / `execute_xxx`（查询用 `get_`，
  编排型动作如摄取、检索用 `execute_`，注册用 `register_`）
- **不要**随意引入新的 `Manager` / `Service` / `Handler` 类名。已有的
  `MCPManager` / `IngestionService` / `RetrievalPipeline` / `QuotaService` 属于既有 Public
  契约，保留不动；新增抽象请优先用 `Store` / `Registry` / `Catalog` / `Pipeline` 这类
  有明确职责边界的词，或直接用模块级函数
- 合并职责相同的函数，不要为一次性逻辑新增函数

### 1.6 Public API 与向后兼容

- `harness/__init__.py` 只导出 7 个稳定符号，**只增不减**：`HarnessApp` / `HarnessConfig` /
  `HarnessPlugin` / `Tool` / `ToolContext` / `load_config` / `tool`
- 已有类的**构造签名只加可选参数**，不要改必填参数或改语义
- 已有 Tool 的 **input_schema 不要改**（模型看到的能力契约）：需要新参数时新增一个 Tool，
  或让新参数可选且不影响旧路径（`build_rag_tool` 就是这样做的）
- HTTP 端点路径与状态码不轻易改；新增端点用新路径

### 1.7 可选依赖必须 Lazy Import

Core 只允许依赖 `openai` / `pydantic` / `python-dotenv` / `jsonschema` / `opentelemetry-api`。
`[rag]` / `[mcp]` / `[observability]` / `[server]` 的导入必须发生在**真正启用的分支**里，
缺失时抛 `FeatureDependencyError`（带可执行安装命令）。

推论（很容易踩）：`chromadb` 只能在 `_register_rag` 的 try 里 import；
`harness/retrieval/catalog.py` 因此**不 import chromadb**，向量库通过
`vector_store_factory` 注入——这样没有 `[rag]` 也能测仓库编排逻辑。

同理，`harness/mcp/client.py` 的官方 SDK 也是延迟导入的（在模块级 import 会让
**整个 MCP 子系统**在没有 `[mcp]` extra 时不可导入，管理器与接口层都无法测试）。
**延迟导入之后必须在组合根补一次启动期检查**（`_register_mcp` 里的显式 `import mcp`），
否则「启用但没装依赖」会从构建期失败退化成第一次发现工具时才失败——那时已经跑在
Worker 里了。`tests/test_mcp_dynamic_tools.py` 里有锁定这个行为的回归测试。

---

## 2. 「能力在运行开始前确定」= 按 Run 快照

0.14.0 起，可复现性不再靠「禁止运行期注册」保证，而是**下沉到 Run 粒度**：

```
AgentRunner.create_execution()
  └─ ToolContext.tool_names = frozenset(当前注册表里的全部工具名)   ← 进 Durable 序列化
        ├─ 模型看到的 schema：registry.openai_schemas(tool_names)    ← 只发快照内的
        └─ 执行准入：ToolContext.tool_names 不含该工具 → TOOL_NOT_IN_RUN_SNAPSHOT
```

因此：

- `ToolRegistry` 分两层。`register(tool)` 是构建期注册，`freeze()` 之后再注册会抛
  `ValueError`；`register(tool, dynamic=True)` 是运行期扩展，可用 `unregister(name)` 摘除。
- **新提交的 Run 才看得到新工具**；已经在跑（或崩溃后恢复）的 Run 仍按原快照执行。
- 想加新的运行期能力时，走 dynamic 层 + 快照，**不要**推翻 `freeze()`。

---

## 3. RAG 多仓库（0.14.0）

### 3.1 隔离模型

一个仓库一个**独立向量集合**（`collection_name = f"repo_{repository_id}"`）。
不用「单集合 + metadata 过滤」：那样删仓库要按 metadata 反选删除，容易误伤别的仓库。

- 仓库与文件元数据：`knowledge_repositories` / `knowledge_repository_files` 两张表，
  由 `harness/retrieval/store.py` 自建（不进入核心 schema）
- 文件原文：`[rag].storage_path`（默认 `data/rag/<repository_id>/<filename>`），
  文件名一律 `Path(filename).name` 归一化，拒绝路径成分
- 旧的单集合路径（`[rag].collection_name` + `tenant_id` 过滤）**完整保留**，
  两条路径共用同一个 `chromadb.PersistentClient`

### 3.2 chunk 元数据的硬契约

每个 chunk **必须**带齐四个字段，缺一个就 `ValueError`（`IngestionService.ingest` 校验）：

| 字段 | 来源 |
| --- | --- |
| `filename` | 调用方（`KnowledgeRepositoryCatalog.execute_ingest`）写入 Document.metadata |
| `repository_id` | 同上 |
| `uploaded_at` | 同上（ISO8601） |
| `embedding_model` | `IngestionService` 从 embedding provider 的**实际生效模型**补齐 |

`document_id = stable_id("doc", f"{repository_id}:{filename}")`：只由仓库+文件名决定，
因此同名文件重新上传会命中同一批 chunk id，先 `delete_by_document` 再写入，旧内容不会残留。

### 3.3 写入授权（复用既有审批，不新造 ACL）

Agent 写入仓库的**唯一**入口是 `harness/app/features.py::create_rag_write_tool`：

- `side_effect=True` + `requires_approval=True` + `required_permissions={"rag.write"}`
- 两道闸门互相独立：权限由 `ToolExecutor` 校验，审批由 `DefaultToolPolicy` +
  持久 `ApprovalStore` 决定；Run 会停在 `APPROVAL_REQUIRED`，用户批准后才落盘建索引
- 不要为 RAG 单独实现一套权限表；仓库级 ACL 属于「以后真需要时再加」的范畴

### 3.4 HTTP 接口（Local 模式，前端用）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/v1/knowledge/repositories` | 仓库列表 |
| POST | `/v1/knowledge/repositories` | 创建仓库（`{name, description}`） |
| GET | `/v1/knowledge/repositories/{id}` | 单个仓库 |
| DELETE | `/v1/knowledge/repositories/{id}` | 删除仓库（含向量集合与文件行） |
| GET | `/v1/knowledge/repositories/{id}/files` | **仓库内文件清单** |
| POST | `/v1/knowledge/repositories/{id}/files?filename=` | 上传并建索引（原始请求体即内容） |

`harness/app/knowledge_api.py` **只注册路由**：错误映射（LookupError→404 / ValueError→400）
与同源保护中间件由 `install_desktop_routes` 统一提供，因此它必须排在后者之后安装。
RAG 未启用时端点仍在，返回 503 + 启用提示（比 404 更好排查）。

---

## 4. MCP 运行期注册（0.14.0）

前端提交 MCP 信息 → 后端自动完成注册，全程不改 Runtime：

```
POST /v1/mcp/servers
  └─ create_server_config()      校验 transport 必填项
  └─ MCPManager.register_server()  建网关 → discover_and_register(dynamic=True)
  └─ SQLiteMCPServerStore.create_server()   只有发现成功才落库
        ↓
  新工具进入注册表动态层 → 只对**之后创建**的 Run 可见（快照）
```

- 持久化的 Server 在 `_register_mcp` 时被重新装载并**在构建期**注册（重启后仍然可用）；
  同名冲突以 `harness.toml` 为准
- `harness.toml` 静态配置的 Server **不能**通过接口删除（`unregister_server` 会拒绝），
  它的工具不是 dynamic 的
- **安全默认**：远端工具的能力声明不被信任。运行期登记的 Server 在用户逐个声明策略之前，
  一律使用 `harness/mcp/config.py::UNTRUSTED_TOOL_POLICY`（`side_effect=True` +
  `requires_approval=True`）。不要把它改成只读默认

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/v1/mcp/servers` | 已生效的 Server 与其贡献的工具（含 `removable`） |
| POST | `/v1/mcp/servers` | 登记并立即发现工具；失败不落库 |
| DELETE | `/v1/mcp/servers/{name}` | 摘除动态 Server 与它的工具 |

---

## 前端导航约束

- 输入框下的指标栏由 `ConversationMetrics.vue` 消费实际 `model.end.metrics` / 模型步骤数据。显示选择存在 appearance store，临时会话的指标不得另行持久化。缓存未知不得当 0%，累计用量不得当上下文占用，窗口余量当前必须标为估算。

- 设置使用原生 dialog 浮窗、左侧分类和右侧内容；使用习惯入口归入设置，旧 `#/preferences` 链接打开对应分类并保留当前对话。使用习惯沿用 `/v1/preferences`，读取失败不得用空白内容覆盖保存。
- 自定义配色仅由 appearance store 验证并保存到浏览器，覆盖现有主题 CSS 变量；恢复配色不影响字体、布局或服务端使用习惯。不新增后端配置或依赖。
- 对话保持居中阅读留白，`ConversationLocator.vue` 根据当前 turns 与实际滚动位置生成右侧定位标记、摘要和跳转；布局变化后更新位置，跳转暂停跟随最新。不得为定位新增 API、历史缓存或临时对话持久化，摘要按纯文本显示。

- 页面地址由 `frontend/src/composables/useWorkbenchRoute.ts` 管理（Hash 路由），刷新不依赖服务端 fallback；对话地址同时携带工作区与会话 ID，并校验所属关系。
- 「项目」文件夹就是现有工作区的界面表示，聊天按 `workspace_id` 分组；不新增 Project 表，不把聊天转存到磁盘目录。
- 插件页只读 MCP；探索页使用真实 RAG 创建、文件上传与索引端点。PR 仍是未接入说明；定时任务已有 Local 调度器，禁止沿用旧占位页。
- `#/chat` 为无工作区普通对话，`#/temporary` 为内存对话，项目对话继续携带工作区 ID。“新对话”入口位于导航最上方，对话列表位于项目下方；项目行新建按钮在展开箭头之前。
- 个人习惯、技能和调度业务在 `app/personal.py`；`PersonalStore` 只做 SQL。`SKILL.md` 导入仅解析 name/description 与 Markdown 正文，不执行附带脚本或路径引用。
- 定时任务统一提交 Durable；对话创建任务、保存偏好都通过需要审批的 Tool。调度 claim 先推进时间再提交，离线补一次，提交中断不自动重放；不可宣称跨进程崩溃下的 exactly-once。
- 临时对话使用组合根创建的同一个 `AgentRunner` 类实例、空工具快照与 Noop 观测，不进入 Durable、数据库、全局事件总线或长期记忆写入。内置 Provider 必须禁用响应留存 / 历史缓存；结束、离开、刷新、关闭页时清除，异常断开最长 30 分钟过期。隐私测试必须覆盖数据库、审计、断连与 Provider 缓存。
- 修改前端后运行 `npm test` 和 `npm run build`，同步 `harness/ui/static/`；验证主题、窄屏、浏览器历史与跨项目会话隔离。已有输入、SSE、审批和隐藏拖动边界应继续可用。

## 5. 固定动作

**改代码前**：读 `README.md` + `docs/architecture.md` + `HANDOFF.md`，并跑一次基线测试。

**改代码后**（顺序固定）：

```bash
pytest -q                     # 必须全绿；注意用 pytest 而不是 python -m pytest
ruff check <你改过的文件>      # 新增代码必须零告警
mypy harness                  # 只要求不新增错误（存量见 HANDOFF 的 baseline）
python -m compileall -q harness tests
```

同时更新：`CHANGELOG.md`（开发中写进 `[Unreleased]`）、必要的 README 端点表，
以及 `HANDOFF.md`（交接状态）。

**不要做的事**：为了「看起来完整」加多租户 UI / OAuth2 / 支付；在没有真实多节点需求前换掉 SQLite；
为一个功能顺手重排全仓代码格式（会把 diff 淹没）。

---

## 6. 已知欠账（选择下一件事时先看这里）

- **精确 token 计算待实施**：见 `docs/token-accounting-plan.md`。当前 `ApproxTokenCounter` 不是精确 tokenizer；完整请求计数、模型版本与窗口确认、Provider 对账和流式速度拆分按该规划推进。
- 按用户要求移除重复的 `AGENTS.md`，保留本文件作为开发指导入口；测试与依赖方向约束继续适用。

1. `harness/retrieval` 与 `harness/mcp` 的连接层仍有欠账：
   `tests/test_optional_integrations.py` 已覆盖真实 MCP STDIO 的发现 / 调用，以及 Chroma
   集合操作；`MCPGateway` 的真实 HTTP 路径还未验证。Core 测试仍可在没有 Extra 时运行
2. `ruff` / `mypy` 从未进 CI，存量告警见 `HANDOFF.md` 的 baseline
3. 前端构建产物（`harness/ui/static`）没有一致性校验 job
4. 依赖没有锁文件；CI 已新增 Python 3.12 的 `.[all,dev]` 作业，远端首次运行仍待验证
