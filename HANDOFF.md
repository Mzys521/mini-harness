# HANDOFF.md — 开发状态交接

> 给下一位接手的人/agent：本文件记录**当前这一轮**做了什么、定了哪些架构决策、
> 实测结果如何、下一步从哪进。架构硬约束见 `AGENT.md`，长期设计见 `docs/architecture.md`。
>
> 阶段：**Phase 14 — Multi-RAG、Runtime MCP 与个人工作台（已完成，0.14.0 已发布）**
> 日期：2026-09-23
> 版本：`0.14.0` 已发布（Phase 1–14 全部完成）；下一轮从下方「Next Task」进入

---

## 当前开发：发布工程与可选依赖集成测试（未发布）

- `.github/workflows/ci.yml` 新增 Python 3.12 `.[all,dev]` 作业，保留原有 3.12/3.13 `.[server,dev]` 作业；在全量作业中先检查 `chromadb` 和 `mcp` 可导入，再执行同一套 `pytest -q`。
- `tests/test_optional_integrations.py` 与 `tests/fixtures/mcp_stdio_server.py` 覆盖真实 MCP stdio 工具发现、注册、调用，以及 Chroma 集合持久化、metadata 过滤、按文档删除、整集合删除与跨仓库隔离。Core 环境无 Extra 时跳过相应测试。
- 本机使用已安装可选包的 pytest 环境跑全量回归：**94 passed / 1 skipped**。新增两项集成测试均实际执行；跳过项是「缺少 MCP Extra 时构建失败」的反向测试。本机另一个 `python` 指向没有 pip 的 MSYS Python，验证应使用与 `pytest` 相同的解释器。
- 仍待 CI 在远端 Python 3.12 全量环境完成首次验证；MCP HTTP 真实传输路径和前端静态产物一致性检查仍是后续任务。

---

## 最新补充：拟定并发布 0.14.0（2026-09-23）

- **版本号定为 `0.14.0`**：Phase 14 新增能力（多 RAG 仓库、运行期 MCP 注册、个人工作台与调度、输入区用量指标）属 minor；两处行为变化（`ToolRegistry.freeze()` 后注册抛 `ValueError`、`IngestionService.ingest()` 元数据校验收紧）已在 CHANGELOG「兼容」一节逐条记录，且**无需数据迁移**（`archived` 列与个人数据表启动时自动补齐）。
- CHANGELOG 的 `[Unreleased]` 收敛为 `## [0.14.0] - 2026-09-23`，补主题摘要、统一小节标题（`### 新增（…）` / `### 变更（…）`）、把「兼容（0.14.0 开发中）」改为「兼容（0.14.0）」，并保留空的 `## [Unreleased]`。
- 版本号四处同步：`pyproject.toml`、`harness/__init__.py`、`frontend/package.json`（含 `package-lock.json` 两处）、README 徽章/阶段数/路线图。README 另补 Phase 14 段落与 P14 模块清单（`knowledge_api` / `mcp_api` / `personal*` / `temporary_chat`、`retrieval/{catalog,store}`、`mcp/store`、`docs/token-accounting-plan.md`）。
- `CONTRIBUTING.md` 新增「版本号与发布」小节：明确 `harness/__init__.py::__version__` 是运行时唯一来源、需要同步的四处位置，以及 `[Unreleased]` → 版本节的发布流程与 `--follow-tags` 推送方式。
- 发布动作：提交本轮全部改动，打标签 `v0.14.0`，推送到 `origin/main`（含标签）。
- **验证与一处测试修复**：`pytest -q` 全量 **95 collected / 94 passed / 1 skipped / 0 failed**（含本轮新加入的可选依赖集成用例；本文件此前记录的 92 passed / 1 skipped 与实测条目数不符，已按实测订正）。
- 过程中发现 `tests/test_conversation_metrics.py::test_metrics_survive_stream_and_history` 的 `duration_ms >= 10` 断言在 Windows 上不稳定。原因**不是指标错误**：探针实测 `await asyncio.sleep(.01)` 在 `perf_counter` 下只有约 **3.7ms**（asyncio 的定时器粒度粗于 `perf_counter`），而 Runner 记录的 `duration_ms` 为 3.79ms，与模型自测耗时一致——说明「窗口确实包住模型调用」，错的是断言的绝对墙钟假设。改为断言「Runner 的窗口不小于模型自测耗时」，语义不变，且不再依赖具体耗时；该文件 Ruff 零告警（`harness/__init__.py` 的 `I001` 为存量）。
- 沙箱记录：pytest 的 `tmp_path` 落在沙箱临时目录下会产生数十项 `PermissionError`，需放宽一次沙箱权限才能跑全量；正常本地环境无此问题。

---

## 最新补充：输入区指标栏（2026-09-23）

- 输入框外侧下方新增 `ConversationMetrics.vue`：11px 小字、16px 行高、线性 SVG 图标，桌面居中单行，窄屏紧凑换行。设置新增「对话指标」，分别控制缓存命中率、输出速度、已用 token、上下文余量、轮数/步数；前四项默认开启，全部关闭隐藏，选择保存在浏览器。
- Runner 在成功模型调用结束时记录 `metrics`（输入/输出/总 token、可空缓存计数、单调时钟耗时、配置窗口），复用 `model.end` 和已有模型步骤持久化；Desktop 透传步骤快照，前端按步骤归并并用事件 seq 防重放。没有新增数据库表、端点或可选依赖，Runner 未增加领域依赖。
- `ModelResult.cache_usage_reported` 默认为 false；内置 Provider 明确报告缓存计数时置 true。DeepSeek 支持原生 `prompt_cache_hit_tokens` 和兼容明细，缺失显示 `—`，报告零可显示 0%。
- 统计口径：缓存、速度、用量属于最近一轮；速度包含首字等待但不含工具/审批等待；上下文余量按配置窗口减去最近一次请求输入和输出，标记 `≈`，不含草稿、不代表模型实际最大窗口。旧记录不补造指标，升级需重启 Local 服务以产生新快照。临时指标沿内存路径随会话清除。
- 按要求移除 `AGENTS.md`，保留 `AGENT.md`；README、CHANGELOG、CONTRIBUTING、架构和交接文档同步。新增 `docs/token-accounting-plan.md`，规划模型感知 tokenizer、完整请求计数、窗口/输出预留、流式速度拆分、重试与 Provider 对账；精确计数尚未实施。
- 验证：前端 41 项通过，类型检查及生产构建通过，静态产物已同步；后端 92 passed / 1 skipped / 3 个既有弃用告警；mypy 保持 178 errors in 12 files（126 个源文件）；compileall、diff 空白检查通过。新增测试文件 Ruff 通过，修改的既有 Python 文件仍有 14 项存量告警，未做无关清理。
- 环境记录：沙箱首次阻止 pytest 临时目录和 Vite 清理旧产物，正常本地环境重跑成功；一次隔离目录回归遇到 Windows 套接字资源不足，最终全量回归通过。浏览器使用 8013 独立测试数据库/替身模型，已检查真实数字、设置入口、桌面和 390px 布局，未修改用户真实会话。

## Completed（实现内容）

### 当前补充：个人工作台（2026-09-22）

本节是当前状态，下文 2026-09-21 的“只读 / 定时未接入”记录是历史状态。

- 按用户确认支持 SKILL.md 文件导入：name/description 描述性元数据 + Markdown 正文；前端可创建、编辑、启停、删除，输入区选择使用；不执行脚本或附带文件。
- 普通对话无需项目/工作区，“新对话”入口置于导航最上方，项目下方保留对话列表；普通会话元数据单独在 `desktop_chats`，继续共享原 Conversation/Run。项目行新建按钮在展开箭头前且共享背景。
- 用户习惯由 `/v1/preferences` 保存，所有 Local 对话提交（包括临时、定时）读取；`remember_user_preference` 默认需批准后追加，无自动推断写入。
- 定时任务可手动创建或通过 `create_scheduled_task` 工具审批创建；支持单次、固定间隔重复、暂停/启用、删除与执行对话链接。`AutomationScheduler` 与 Local Worker 同生命周期，claim 使用条件 SQL；离线补一次，提交中断标记 interrupted，不静默重放。
- 临时会话按用户确认：结束、离开、刷新、关闭后清除；生成断连取消，未收到关闭通知的闲置会话最长 30 分钟过期。独立内存 SSE、不落库、不进入审计/broker/长期记忆，最多 100 会话，每会话最近 20 条消息；OpenAI `store=false`，DeepSeek 不写 `_histories`。第三方 Provider 与远端服务商留存需遵守各自契约。
- 探索页创建 RAG 仓库、上传 UTF-8 文本并查看索引；复用此前已有后端，不改 Chroma / MCP 子系统。PR 仍无管理后端，MCP UI 仍只读。
- 新增后端：`personal_store.py`、`personal.py`、`personal_api.py`、`temporary_chat.py`；前端新增 `PersonalPage.vue`、`ChatList.vue`。唯一组合根仍为 assembly，未给 Runner 增加功能分支，无新增依赖。
- 本轮前端基线 30 项，完成后 35 项通过；类型检查和生产构建通过，静态产物已同步。后端基线 76 passed / 1 skipped；新增 9 项个人功能测试通过；最终全量 85 passed / 1 skipped / 3 个既有依赖弃用告警。compileall 与 diff 空白检查通过。
- 隔离临时数据库 + ScriptedModel 的浏览器验收已检查普通入口、桌面临时虚线样式、临时收发、离开清理、技能保存及定时任务手动创建；没有对真实用户数据发写请求，没有使用外部模型凭据。
- `mypy harness` 保持 178 errors in 12 files（126 源文件），新增模块无类型错误；新增 Python 模块和测试 Ruff 通过；全仓 harness/tests 审计为 144 项（基线 145，整理组合根导入减少 1 项）。既有 Ruff/mypy 欠账不在本轮清理范围。

后续注意：定时需要 Local 服务在线；无操作系统唤醒、通知推送或 cron 表达式。停用/删除被任务引用的技能会使后续提交失败，需要恢复技能或重建任务；暂停不会取消已提交的 Run。临时浏览器关闭请求是尽力发送，TTL 是异常断连兜底。

### 1. 工具能力按 Run 快照固定（为运行期注册铺路）

- `ToolContext` 新增可选字段 `tool_names`（`None` = 不限制），并进入 Durable 序列化
  （`execution_to_dict` / `execution_from_dict` 双向 round-trip）
- `AgentRunner.create_execution()` 在创建 Run 时把当前工具名集合写入快照
- 模型只看到快照内的 schema（`registry.openai_schemas(names)`）；`ToolExecutor` 拒绝
  快照外的调用（新错误码 `TOOL_NOT_IN_RUN_SNAPSHOT`，状态仍为 `NOT_FOUND`）
- `ToolRegistry` 分两层并真正封板：`register(tool)` 构建期 / `freeze()` 后抛 `ValueError`；
  `register(tool, dynamic=True)` 运行期 + `unregister(name)` / `is_dynamic(name)`
- 组合根在注册完 RAG / MCP 工具后调用 `registry.freeze()`

### 2. 多 RAG 仓库

- 新增 `KnowledgeRepositoryCatalog`（`harness/retrieval/catalog.py`）：创建 / 查询 / 删除仓库，
  文件摄取与仓库内检索。**一个仓库一个独立向量集合**，删除仓库即丢弃整份集合
- 新增 `SQLiteKnowledgeRepositoryStore`（`harness/retrieval/store.py`）：`knowledge_repositories`
  与 `knowledge_repository_files` 两张表，`(repository_id, filename)` 唯一 → 同名重传为覆盖
- chunk 元数据硬契约：`filename` / `repository_id` / `uploaded_at` / `embedding_model` 缺一即
  `ValueError`；`embedding_model` 取自 provider 的实际生效模型
- `document_id` 只由「仓库 + 文件名」派生，重传先 `delete_by_document` 再写入，旧内容不残留
- 新增 `create_rag_write_tool()`：Agent 写入仓库的唯一入口，`side_effect=True` +
  `requires_approval=True` + `required_permissions={"rag.write"}`（复用 Phase 9 审批，**不新增权限表**）
- `build_rag_tool()` 新增可选 `catalog`：传入后支持按 `repository_id` 检索；
  **不传时 schema 与行为与旧版逐字一致**
- `[rag]` 新增 `storage_path`（默认 `data/rag`）与 `write_tool_name`（默认 `rag_write_file`）

### 3. 运行期 MCP 注册

- 新增 `SQLiteMCPServerStore`（`harness/mcp/store.py`）：前端登记的 Server 持久化，
  重启后由 `_register_mcp` 重新装载并在构建期注册（同名冲突以 `harness.toml` 为准）
- `MCPManager` 扩展（**没有新增类名**）：`register_server()` / `unregister_server()` /
  `get_server_tools()`。静态配置的 Server 拒绝运行期删除
- `MCPServerConfig` 新增 `default_tool_policy`；新增 `UNTRUSTED_TOOL_POLICY`
  （`side_effect=True` + `requires_approval=True`）作为运行期登记的保守默认
- `discover_and_register()` 新增 `dynamic` 关键字参数（默认 `False`）
- **`pytest` 无跳过**：`POST /v1/mcp/servers` 的端到端用例跑的是**真实 `MCPManager`**
  （只有「连远端」用替身网关），因此注册表动态层、工具归属、落库与摘除都是真代码路径
- 注册顺序保证一致性：**先发现成功再落库**，失败不留连不上的配置
- **官方 SDK 改为延迟导入**（`harness/mcp/client.py`）：原先模块级 `from mcp import ...`
  让整个 MCP 子系统在没有 `[mcp]` extra 时不可导入，管理器与接口层都无法测试。
  改为使用时导入 + 可执行安装提示；`_register_mcp` 保留一次显式 `import mcp` 启动期检查，
  「启用但没装 extra」仍在**构建期**抛 `FeatureDependencyError`，并有回归测试锁定

### 4. HTTP 接口（Local 模式，供前端）

RAG：`GET|POST /v1/knowledge/repositories`、`GET|DELETE /v1/knowledge/repositories/{id}`、
`GET /v1/knowledge/repositories/{id}/files`、`POST /v1/knowledge/repositories/{id}/files?filename=`

MCP：`GET|POST /v1/mcp/servers`、`DELETE /v1/mcp/servers/{name}`

两者在对应 Extra 未启用时返回 **503 + 启用提示**（而不是 404）；
只注册路由，错误映射与同源保护复用 `install_desktop_routes`，因此安装顺序必须在其之后。

### 5. 文档

- 新建 `AGENT.md`（架构硬约束、依赖方向矩阵、命名、Phase 14 设计、固定动作、欠账）
- 新建本文件
- `CHANGELOG.md` 在 `[Unreleased]` 下补三节新增与一节变更 + 兼容说明
- `README.md`：Local 模式端点表补 9 行、能力表更新 retrieval / mcp 行、路线图补 Phase 14（开发中）、
  项目结构补 `AGENT.md` / `HANDOFF.md`

---

## Modified Files

**新增**

| 文件 | 作用 |
| --- | --- |
| `AGENT.md` | 给后续 agent 的施工规范 |
| `HANDOFF.md` | 本文件 |
| `harness/retrieval/catalog.py` | 多 RAG 仓库编排（create/get/list/delete/execute_ingest/execute_search） |
| `harness/retrieval/store.py` | 仓库与文件元数据的数据访问层 |
| `harness/mcp/store.py` | 前端登记的 MCP Server 持久化 |
| `harness/app/knowledge_api.py` | RAG 仓库 HTTP 路由 |
| `harness/app/mcp_api.py` | MCP Server HTTP 路由 + 请求体校验 |
| `tests/test_knowledge_repositories.py` | 11 个用例：隔离 / 元数据 / 覆盖 / 越界 / 授权 / HTTP |
| `tests/test_mcp_dynamic_tools.py` | 8 个用例：注册表封板 / 快照 / 持久化 / 策略 / HTTP |

**修改**

| 文件 | 改动 |
| --- | --- |
| `harness/tools/registry.py` | 两层注册 + `freeze()` / `unregister()` / `is_dynamic()` / `openai_schemas(names)` |
| `harness/tools/definition.py` | `ToolContext.tool_names` |
| `harness/tools/executor.py` | 快照准入检查 |
| `harness/runner.py` | 创建 Run 时写快照；模型 schema 按快照过滤 |
| `harness/durable/serialization.py` | `tool_names` 双向序列化 |
| `harness/retrieval/models.py` | `KnowledgeRepository` / `KnowledgeRepositoryFile` / `REQUIRED_CHUNK_METADATA` |
| `harness/retrieval/ingestion.py` | 补齐并校验四个必填元数据 |
| `harness/retrieval/chroma_store.py` | 可选共享 `client`、`collection_name`、`delete_all()` |
| `harness/retrieval/vector_store.py` | 协议新增 `delete_all()` |
| `harness/mcp/config.py` | `default_tool_policy` + `UNTRUSTED_TOOL_POLICY` |
| `harness/mcp/discovery.py` | `dynamic` 参数；使用 `default_tool_policy` |
| `harness/mcp/manager.py` | `register_server()` / `unregister_server()` / `get_server_tools()` |
| `harness/mcp/client.py` | 官方 SDK 改为延迟导入（`_load_mcp_sdk()`），缺失时给出安装命令 |
| `harness/app/features.py` | `create_rag_write_tool()`；`build_rag_tool()` 支持 catalog |
| `harness/app/config.py` | `[rag].storage_path` / `[rag].write_tool_name` |
| `harness/app/assembly.py` | 装配 Catalog 与 MCP store/manager，注册写工具，`registry.freeze()`，MCP 启动期依赖检查 |
| `harness/app/runtime.py` | `RuntimeBundle` 新增 `knowledge` / `mcp` / `mcp_store` |
| `harness/app/server.py` | 挂载两个新路由模块 |
| `README.md` / `CHANGELOG.md` | 见上 |

> 另外对 `harness/retrieval/{models,ingestion,chroma_store,vector_store}.py`、
> `harness/mcp/{config,discovery}.py`、`harness/tools/{registry,executor}.py` 等文件做了
> **ruff 驱动的空行/导入规范化**（每个文件 1–2 行），不是功能改动。

**P14 后端阶段未触碰**：`frontend/**` 与 `harness/ui/static/**`。随后前端导航任务已修改并重新构建这两个目录，见下方补充。

---

## Architecture Decisions

### 依赖方向（硬约束，已逐条核实）

```
harness/app/*  →  cli  →  {retrieval, mcp, platform, evaluation}  →  {runner, tools, context, durable, security}  →  {persistence, state, models, streaming}
```

- `harness/runner.py` 的 import 面**只有**：`context.models` / `durable.models` / `models` /
  `streaming` / `tools.result`。没有 `app` / `retrieval` / `mcp` / `platform` / `persistence` / `security`
- `harness/retrieval/*` 与 `harness/mcp/*` **没有**任何 `from harness.app|platform|evaluation|observability`
  （grep 验证为空）
- `harness/persistence/*` **不含** `knowledge_repositories` / `mcp_servers` 字样：可选能力的表由各自模块自建，
  因此关掉 `[rag]` 时核心 schema 不变
- 组合根唯一：`harness/app/assembly.py`

### 为什么「可复现性」下沉到 Run 快照

原来靠「build 后禁止注册」（`HarnessApp._ensure_mutable` 抛 `RuntimeError`）保证，
但它与「前端提交 MCP 信息后自动注册」直接冲突。选择**保留 build 快照 + 增加动态层 + 按 Run 快照**：

- build 期能力仍是确定集合，`freeze()` 让约束从「门面约定」变成「注册表自身行为」
- 运行期新增只影响**之后创建**的 Run；在跑或崩溃恢复的 Run 按 `ToolContext.tool_names` 执行
- 快照进 Durable 序列化，所以恢复后的 Run 不会突然多出能力

### 为什么 RAG 用「一仓库一集合」而不是 metadata 过滤

删除仓库必须干净且不能误伤其他仓库。metadata 过滤需要按条件反选删除，漏一个字段就残留；
独立集合让删除退化成 `delete_collection`，同时天然构成租户/仓库隔离。

### 为什么写入授权复用审批而不是新增 ACL 表

需求是「Agent 仅在用户授权后才能写入」。Phase 9 已经有确定性的 Tool Policy + 持久 ApprovalStore
（跨进程可恢复、前端已有批准/拒绝按钮）。新增仓库级 ACL 会引入第二套权限真相来源，
与「权限由服务端从声明解析」的既有模型冲突。仓库级 ACL 列为后续任务。

### 为什么 `catalog` 不 import chromadb

`[rag]` 是可选依赖，CI 只装 `.[server,dev]`。把向量库改成注入的 `vector_store_factory` 后，
仓库编排逻辑（隔离、元数据、覆盖、越界）在没有 chromadb 的环境里也能测——本轮 11 个 RAG 用例
正是这样跑起来的。同时向量后端整体可替换。

### 为什么 `mcp/client.py` 改成延迟导入 SDK

同一个理由的另一半：模块级 `from mcp import ...` 让**整个 MCP 子系统**（`MCPManager`、
`SQLiteMCPServerStore`、`harness/app/mcp_api.py`）在没有 `[mcp]` extra 时都不可导入，
于是「前端提交 MCP 后自动注册」这条链路一次也测不到。延迟导入之后：
管理器可以用替身网关上真实用例；`_register_mcp` 的启动期检查保证缺依赖仍然在构建期失败。
代价是 `mypy` 多一处 `import-not-found`（与同文件里 `chromadb` 那处同类，属缺可选依赖 stub 的存量问题）。

### 安全默认

运行期登记的 MCP Server，其远端工具在用户逐个声明策略前一律
`UNTRUSTED_TOOL_POLICY`（有副作用 + 需要审批）。**不要**把它改成只读默认：
远端工具的能力声明不可信，这是本仓库既有的安全立场（见 `SECURITY.md`）。

---

## Compatibility

### 旧 Public API：全部保留

- `harness/__init__.py` 的 7 个导出符号一个没动
- `ToolRegistry.register(tool)` / `get()` / `list_tools()` / `openai_schemas()` 旧调用方式不变
  （`openai_schemas` 只是多了可选参数）
- `ToolContext` / `MCPServerConfig` / `RuntimeBundle` 只**新增带默认值的字段**
- `IngestionService` 构造签名未变（全仓检索确认此前**零调用方**，因此 `ingest()` 收紧校验无影响）
- `build_rag_tool()` 不传 `catalog` 时 schema 与行为与旧版一致（另建了一个 args model，
  没有改旧 schema）
- `discover_and_register()` 新参数有默认值；`QuotaService` 等 0.13 的兼容门面未动
- HTTP：既有端点路径与状态码未变，新增 9 个端点

### 行为变化（需要注意的两处）

1. **注册表封板**：build 之后直接调用 `registry.register()`（绕过 `HarnessApp` 门面）现在抛
   `ValueError`，此前静默允许。门面层 `app.add_tool()` 的 `RuntimeError` 行为未变
2. **`IngestionService.ingest()` 会在元数据不全时抛 `ValueError`**（此前静默写入残缺索引）

### 新增 API（公开面）

| 层 | 新增 |
| --- | --- |
| 工具层 | `ToolRegistry.freeze()` / `unregister()` / `is_dynamic()`；`ToolContext.tool_names` |
| RAG | `KnowledgeRepositoryCatalog`、`SQLiteKnowledgeRepositoryStore`、`KnowledgeRepository`、`KnowledgeRepositoryFile`、`create_rag_write_tool()`、`VectorStore.delete_all()` |
| MCP | `SQLiteMCPServerStore`、`MCPManager.register_server()` / `unregister_server()` / `get_server_tools()`、`UNTRUSTED_TOOL_POLICY`、`MCPServerConfig.default_tool_policy` |
| HTTP | 见上「Completed 4」 |
| 配置 | `[rag].storage_path`、`[rag].write_tool_name` |
| Runtime | `RuntimeBundle.knowledge` / `.mcp` / `.mcp_store` |

---

## Tests

用**与 CI 相同的调用方式**执行（`pytest`，不是 `python -m pytest`）。

| 项目 | 结果 |
| --- | --- |
| `pytest -q` | **77 passed, 0 skipped**（上一轮基线 56 passed；本轮新增 21 个用例，无跳过） |
| `python -m compileall -q harness tests` | 通过 |
| `ruff check`（ruff 0.16.1，仓库 `pyproject.toml` 配置） | 全仓 **160 errors**（本轮改动前 166 → 净减 6，且新增了约 900 行代码）。**本轮新建的 5 个模块与 2 个测试文件全部 `All checks passed`**；仅 `knowledge_api.py` / `mcp_api.py` 各留 1 处 `B008`（FastAPI `Body(...)` 默认值），与仓库既有 `server.py` / `api.py` 写法一致，属有意保留 |
| `ruff check --select E4,E7,E9,F`（dev 依赖声明的经典集） | 全仓 **26 errors**，**全部是 `F401` 未使用导入**，均在既有文件里 |
| `mypy harness` | **198 errors in 14 files**（本轮改动前 225 errors in 17 files）。新增的 5 个模块与 2 个测试文件零类型错误；198 里的 **1 处来自有意为之的 `import mcp` 启动期检查**（`assembly.py:216`，与同文件 `chromadb` 那处同类：缺可选依赖 stub）。过程中在自己新写的测试里发现并修掉 3 处 `SimpleNamespace` 顶替 Pydantic 模型的 `arg-type` |

### 存量 baseline（本轮未修，按约定只记录）

- `ruff`：`I001` 85 处（顶层定义前只空一行，属全仓既有风格）、`F401` 26、`B008` 16（FastAPI 默认参数）、
  `UP035` 8、`UP037` 6，其余零散
- `mypy`：225 → 198，**167 处集中在 `providers/openai_provider.py`**（openai SDK 重载），
  其余分布在 `observability/bootstrap.py`、`persistence/unit_of_work.py`、`app/assembly.py` 等既有文件
- 两个工具在本仓库**从未进过 CI**，因此这些数字第一次被记录；`AGENT.md` 第 6 节把它们列为欠账

---

## Next Task

### 建议入口（按性价比排序）

1. **让 `[rag]` / `[mcp]` 真正进 CI**（已实现，待远端 CI 首次验证）
   - 入口：`.github/workflows/ci.yml`
   - 已加 Python 3.12 + `pip install -e ".[all,dev]"` matrix 作业，并检查两个 Extra 的导入
   - 收益：`MCPGateway` 连 HTTP / STDIO 的真实路径、`ChromaVectorStore` 的真实集合操作
     第一次进 CI（本轮已用替身把编排逻辑覆盖掉，剩下的就是这一层）
   - 本机 pytest 环境已有两个 Extra，真实集成测试通过；远端 CI 尚待首次运行

2. **补远端连接层的测试**
   - MCP：本地 stdio 真实链路已覆盖；仍需验证真实 HTTP 传输
   - RAG：Chroma 集合真实读写已覆盖；仍需补 `execute_search` 的排序与 top_k 语义
   - 失败回滚：`register_server` 在发现失败时不应落库，目前只有 HTTP 层的替身覆盖了这一点

3. **把 ruff / mypy 加进 CI 并冻结 baseline**
   - 入口：`.github/workflows/ci.yml` + `pyproject.toml`
   - 先只开 `E4,E7,E9,F`（26 处 F401，可一次性 `--fix`），再用 `--statistics` 逐步扩大
   - `mypy` 建议先按文件白名单渐进（例如只对 `harness/tools`、`harness/retrieval`、`harness/app` 生效）

4. **前端补充管理操作**
   - RAG：列表、创建、文件上传和索引清单已完成；仓库删除 UI 待后续明确需求
   - MCP：已有 Server / 工具列表；待做添加表单 / 删除
   - 注意前端构建产物 `harness/ui/static` 需要重新构建并入库

5. **仓库级 ACL（可选，先别急）**
   - 当前「用户授权」= 现有审批流；如果真要按仓库逐个授权，入口是
     `KnowledgeRepository.owner_user_id` + `ToolContext.permissions` 里加 `rag.write:<repo_id>`
   - 动之前先读 `AGENT.md` 第 3.3 节的理由

### 明确不要做

- 不要为了「看起来完整」加多租户 UI / OAuth2 / 支付集成
- 不要在出现真实多节点需求前把 SQLite 换掉
- 不要 `ruff --fix` 全仓（会让 diff 淹没功能改动；I001 是既有风格，单独一次提交再处理）


## 前端导航与项目会话补充（2026-09-21）

- 已按 AGENT / HANDOFF / README 的边界，以现有 Vue/Pinia 和 API 完成侧栏路由与项目会话树；不改后端、数据库或依赖。
- `useWorkbenchRoute.ts`：`#/chat?workspace=…&session=…`、`#/pull-requests`、`#/automations`、`#/plugins`、`#/explore`；可刷新、前进/后退、直接打开，未知页面与无效会话有明确状态。
- `ProjectTree.vue` 与 `stores/chat.ts`：工作区显示为项目文件夹，会话分组缓存、独立展开；新建/归档/恢复/删除继续使用已有接口，操作目标绑定工作区。这里的「目录」是界面层级，聊天仍在 SQLite，不向工作区磁盘写入聊天文件。
- `CapabilityPage.vue`：只读接入 MCP 服务/工具、RAG 仓库/文件列表；加载、空状态、失败与重试完整。PR/定时任务暂无后端，仅显示说明；未新增语音等不受支持的操作。
- 既有外观设置、衬线字体、统一 Logo、圆角输入区与隐藏拖动边界保留；聊天和代码滚动条使用主题细圆角样式、透明轨道与悬停强调，高对比模式保留系统样式。
- 同步文档：AGENT、HANDOFF、README、CHANGELOG、CONTRIBUTING、docs/architecture；历史版本迁移文档不改。
- 本机旧服务的 MCP/RAG 接口返回 404，界面会提示重启更新后的 Local 服务；未擅自重启用户正在运行的服务。真实成功数据与 503/重试路径由前端 API 替身验证。

### 本次验证（前端任务）

- 修改前前端 23 项通过；修改后 30 项通过，包含多项目归属、直接链接、后退、非当前项目归档、草稿/SSE 保留、能力页读取与失败重试。
- `pytest -q -rs`：76 passed、1 skipped、3 个依赖弃用告警，与本轮开始基线一致。跳过项为缺少 MCP extra 的启动检查：当前环境已安装该依赖，故不能验证缺依赖分支；不是运行期注册用例跳过。
- 本轮没有修改 Python；`ruff check harness tests --statistics` 审计为 145 个既有告警（此范围不含 app_tools/scripts，不能直接与上方全仓 160 比较）。
- `mypy harness`：178 errors in 12 files（122 个源文件），仍为 Python 存量错误；本次未改 Python。不同依赖环境下数量与前述后端阶段记录不同。
- `python -m compileall -q harness tests`、`npm run build`（含 TypeScript 检查）与 `git diff --check` 通过，`harness/ui/static/` 已重新生成。
- 浏览器已验证深色/浅色/纸张主题、390px 窄屏无横向溢出、多个项目同时展开、导航页面、聊天细滚动条与旧服务接口提示。


### 项目新建入口样式补充

项目标题行使用悬浮加号，项目行使用悬浮方框铅笔按钮；离开对应行即隐藏，保留键盘可见焦点与无悬浮设备入口。仅调整 ProjectTree、AppIcon 和 CSS，不增加菜单或后端操作；README、CHANGELOG 与静态构建同步更新。

验证：前端 30 项通过、类型检查与构建通过；pytest 76 passed / 1 skipped；mypy 178 errors in 12 files，与前次存量一致；compileall 通过。未改 Python，Ruff 无本次适用文件。已在实际构建页面确认默认三个入口 opacity=0，悬浮项目行仅该行图标为 1，移到项目标题则仅加号为 1。


### 新对话入口与临时对话图标（2026-09-22）

“新对话”主入口移至侧栏导航第一项（Pull Request 上方），普通对话列表仍在项目下方。右上角临时对话按钮改为虚线气泡 SVG，保留 title、aria-label 与按下状态，开启时高亮。前端 35 项测试、类型检查与生产构建通过；未修改后端逻辑。
本次完整回归：pytest 85 passed / 1 skipped；mypy 保持 178 errors in 12 files；compileall 通过。

### 设置浮窗、自定义配色与对话定位（2026-09-22）

- 使用习惯移入左下角设置，设置采用原生 dialog 浮窗，左侧为外观与字体、自定义配色、使用习惯，右侧独立滚动；保留分类切换中的偏好草稿。旧 `#/preferences` 链接打开对应分类，保留当前聊天/临时对话。偏好读取失败时不显示空白保存表单。
- appearance store 在原浏览器存储键上兼容新增强调色和背景/面板/正文/边框颜色；六位 HEX 校验、预设强调色、对比度提示、自动按钮文字明暗和恢复主题配色均已实现。恢复颜色不影响字体、布局或服务端偏好。
- 对话正文及输入区最大 880px，居中并增加左右与轮次留白。`ConversationLocator.vue` 右侧短横线按轮次排列，悬浮/聚焦展示提问、回复摘要和状态；点击定位、暂停自动跟随，滚动/布局变化更新高亮。支持键盘与减少动画偏好，空对话隐藏，不新增 API 或持久化。
- 此次仅修改前端及文档，保留工作区中已有的后端改动；同步 README、AGENT、HANDOFF、CHANGELOG、CONTRIBUTING 和架构文档，静态构建已更新。
- 验证：前端 39 项测试通过；TypeScript 检查和生产构建通过；pytest 85 passed / 1 skipped / 3 个既有依赖弃用告警；mypy 178 errors in 12 files（126 个源文件），基线未变。本轮未改 Python，Ruff 无新增适用文件。
- 浏览器使用独立 ScriptedModel 临时数据库与 8012 预览服务验证：8 轮会话定位、摘要、当前高亮、回到最新入口，以及 390px 下的设置三分类和聊天布局，无页面横向溢出；未修改真实用户会话。
