# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 测试与持续集成

- CI 保留 Python 3.12/3.13 的常用依赖作业，新增 Python 3.12 `.[all,dev]` 作业，并在测试前检查 RAG/MCP 可选依赖确实可导入。
- 新增真实 MCP stdio 服务器的发现、注册与调用测试，以及 Chroma 集合的持久化、过滤、按文档删除和仓库隔离测试；未安装对应 Extra 的 Core 环境会跳过这些集成用例。

## [0.14.0] - 2026-09-23

> 主题：**多 RAG 仓库、运行期 MCP 与个人工作台（Multi-RAG, Runtime MCP & Personal Workbench）**。Phase 1–13 的能力全部保留：RAG 从「单集合 + `tenant_id` 过滤」扩展为**多个相互隔离的仓库**（一仓库一份向量集合，Agent 写入需用户审批）；MCP 从「启动期静态配置」扩展为**前端登记即发现并注册**；工具注册表在 build 期 `freeze()` 封板之上增加**运行期动态层**，并把「这次运行能用哪些工具」固定进 Run 快照。工作台一侧补上普通对话、临时对话、技能、使用习惯与定时任务。
> **无需数据迁移**：会话归档列（`archived`）与个人数据表都在启动时自动补齐，旧工作区数据照常可用。本版有两处**行为变化**，见下「兼容」。

### 新增（输入区对话指标）

- 输入框下增加小字、SVG 图标和紧凑行高的用量栏；设置中可选择缓存命中率、输出速度、已用 token、上下文余量与轮数/步数，全部关闭可隐藏。
- 模型请求结束事件和历史步骤携带用量、耗时、配置窗口；缓存未报告与报告零区分，兼容 DeepSeek 原生缓存计数。旧数据保留未知值，临时指标不落盘。
- 上下文余量明确为估算；新增 [docs/token-accounting-plan.md](docs/token-accounting-plan.md) 规划模型感知 tokenizer、完整请求计数及 Provider 用量对账。
- 按用户要求移除 `AGENTS.md`，保留并更新 `AGENT.md`。

### 变更（设置浮窗与对话阅读）

- 使用习惯并入左下角设置；设置改为左侧分类、右侧内容的浮窗，兼容旧偏好页面链接，保留聊天草稿和分类内编辑内容。
- 新增自定义强调色和背景/面板/文字/边框配色，支持拾色器、六位 HEX 校验、对比度提示、即时预览、浏览器保存与恢复主题颜色。
- 对话增加居中阅读留白，右侧以短横线提供逐轮定位；悬浮或聚焦展示提问、回复摘要及状态，点击跳转并暂停跟随最新，滚动时高亮当前轮次，支持键盘和减少动画偏好。

### 新增（Local 个人对话与自动化）

- 项目之外的普通对话与独立列表；临时对话支持流式回答，虚线边框，结束/离开/刷新/关闭清除，异常断开最长 30 分钟过期；不写入本地会话、运行、审计或长期记忆，内置 Provider 禁用响应留存/历史缓存。
- 个人使用习惯读取与编辑，普通/项目对话可审批后保存偏好；技能创建、编辑、启停、删除、SKILL.md 指令导入与对话选用，不执行脚本。
- Local 定时任务真实调度：手动或对话审批后创建，单次/固定间隔、暂停/启用/删除、查看执行对话；服务离线积压只补一次，工具副作用继续审批。
- 探索页可创建 RAG 仓库、上传 UTF-8 文本并查看索引结果；保留未启用时的配置提示。

### 变更（侧栏与会话入口）

- 普通“新对话”入口置于导航最上方，对话列表保留在项目下方；临时对话使用虚线气泡图标；项目行新建会话位于展开箭头之前，共用行背景，保留悬浮与键盘入口。
- `POST /v1/sessions` 的工作区现为可选，未指定的列表查询返回普通会话；`POST /v1/runs` 支持技能选择，普通会话工具限制为调度与偏好保存。新增 `desktop_chats` 及个人上下文/调度表，旧工作区数据无需迁移。

### 新增（前端导航与项目会话）

- 项目标题的新建工作区按钮、项目行的新建会话按钮在鼠标悬浮对应行时显示，分别采用加号与方框铅笔图标；预留按钮位置避免文字跳动，键盘焦点和触屏仍可操作。

- 左侧新增新对话、Pull Request、定时任务、插件、探索入口；使用原生 Hash 路由，支持直接地址、刷新与浏览器前进/后退，不增加依赖。
- 「项目」下每个文件夹复用一个工作区，会话按 `workspace_id` 嵌套显示、独立展开；新建、归档、恢复和删除沿用已有接口，不增加数据库表或聊天文件存储。
- 插件页读取 MCP 服务/工具清单，探索页提供知识库/文件管理，包含加载、空状态和失败重试；PR 保留未接入说明，定时任务已接入本地调度。
- 保留左下角外观设置、默认衬线字体、项目统一 Logo、圆角输入区与隐藏的可拖动边界；聊天/代码滚动条改为主题自适应的细圆角样式，悬停突出显示，高对比模式沿用系统样式。
- 新增导航、跨工作区隔离、历史地址、非当前项目归档、草稿/事件流保留、MCP/知识库读取与重试回归测试。

### 新增（多 RAG 仓库）

- **一个仓库一个独立向量集合**：`KnowledgeRepositoryCatalog`（`harness/retrieval/catalog.py`）管理多个相互隔离的 RAG 仓库，`collection_name` 由仓库 id 派生（`repo_<id>`）。删除仓库 = 丢弃整份集合，不必按 metadata 反选删除，也不会误伤别的仓库
- **仓库与文件元数据落 SQLite**：`knowledge_repositories` / `knowledge_repository_files` 两张表由 `harness/retrieval/store.py` 自建（**不进入核心 `persistence/schema.py`**：关掉 `[rag]` 时不该在核心里留下只属于它的表）。唯一约束 `(repository_id, filename)` 让同名重传成为覆盖
- **chunk 元数据硬契约**：每个 chunk 必须带齐 `filename` / `repository_id` / `uploaded_at` / `embedding_model`，缺一个 `IngestionService.ingest()` 直接抛 `ValueError`。前三个由调用方写进 `Document.metadata`，`embedding_model` 由摄取服务从 provider 的**实际生效模型**补齐
- **同名重传不残留**：`document_id = stable_id("doc", f"{repository_id}:{filename}")` 只由仓库 + 文件名决定，重传时先 `delete_by_document` 再写入，旧内容不会留在索引里
- **Agent 写入需用户授权**：`create_rag_write_tool()`（`harness/app/features.py`）是唯一入口，声明 `side_effect=True` + `requires_approval=True` + `required_permissions={"rag.write"}`。两道闸门独立生效：权限由 `ToolExecutor` 校验，审批由 `DefaultToolPolicy` + 持久 `ApprovalStore` 决定，Run 停在 `APPROVAL_REQUIRED` 等用户批准。**没有新增权限表**，沿用 Phase 9 的既有机制
- **前端接口**：`GET/POST /v1/knowledge/repositories`、`GET/DELETE /v1/knowledge/repositories/{id}`、`GET /v1/knowledge/repositories/{id}/files`（仓库内文件清单：文件名 / chunk 数 / 向量化模型 / 上传时间）、`POST /v1/knowledge/repositories/{id}/files?filename=`（原始请求体即内容）。`[rag]` 未启用时端点返回 503 + 启用提示，而不是让前端猜 404
- **向量后端改为注入**：`KnowledgeRepositoryCatalog` 通过 `vector_store_factory` 拿向量库，**不 import chromadb**。因此没有 `[rag]` extra 也能导入并测试仓库编排逻辑（`[rag]` 之外不再需要为了跑测试装 chromadb）
- **旧路径完整保留**：`[rag].collection_name` + `tenant_id` 过滤的单集合检索行为与 schema 都不变；`build_rag_tool()` 的 schema 在未传 catalog 时与旧版逐字一致（多仓库检索走另一个 args model）

### 新增（运行期 MCP 注册）

- **前端提交 MCP 信息即自动注册工具**：`POST /v1/mcp/servers` → 建网关 → 发现远端工具 → 注册进注册表动态层 → 落库。**发现失败不落库**，不会留下连不上的配置
- **`SQLiteMCPServerStore`**：登记过的 Server 在重启后由 `_register_mcp` 重新装载并在**构建期**注册（同名冲突以 `harness.toml` 为准），因此静态配置与前端登记共用一条装配路径
- **`MCPManager` 扩展（既有类，未新增类名）**：`register_server()` / `unregister_server()` / `get_server_tools()`。`harness.toml` 静态配置的 Server 拒绝运行期删除，它的工具不是 dynamic 的
- **安全默认**：远端工具的能力声明不被信任。运行期登记的 Server 在用户逐个声明策略之前一律使用 `UNTRUSTED_TOOL_POLICY`（`side_effect=True` + `requires_approval=True`），宁可多一次审批也不把未知远端工具当只读执行
- **官方 SDK 改为延迟导入**：`harness/mcp/client.py` 原本在模块级 `from mcp import ...`，导致没有 `[mcp]` extra 时**整个 MCP 子系统**（管理器、Server 清单存储、接口层）都不可导入、也无法测试。现在 SDK 在真正使用时才导入并给出可执行安装命令；`_register_mcp` 另外保留一次显式 `import mcp` 启动期检查，因此「启用 MCP 但没装 extra」仍然在**构建期**抛 `FeatureDependencyError`（新增回归测试锁定这个行为）
- **`GET/DELETE /v1/mcp/servers`**：列出已生效的 Server 与其贡献的工具（含 `removable` 标记）／摘除动态 Server。`[mcp]` 未启用时返回 503 + 启用提示

### 变更（工具注册表：构建期封板 + 运行期动态层）

- **可复现性下沉到 Run 粒度**：`AgentRunner.create_execution()` 把当时的工具名集合写进 `ToolContext.tool_names`（并进入 Durable 序列化）。模型只看到快照内的 schema，执行器也会拒绝快照外的调用（`TOOL_NOT_IN_RUN_SNAPSHOT`）。**新提交的 Run 才看得到运行期新增的工具**，已经在跑或崩溃恢复的 Run 仍按原快照执行
- **`ToolRegistry` 两层**：`register(tool)` 是构建期注册，`freeze()` 之后再注册抛 `ValueError`（此前这条规则只在 `HarnessApp` 门面上，注册表本身没有封板）；`register(tool, dynamic=True)` 是运行期扩展，配套 `unregister(name)` / `is_dynamic(name)`。`openai_schemas(names=None)` 新增可选快照参数，不传时语义与旧版一致
- **`MCPToolPolicy` 默认值可声明**：`MCPServerConfig` 新增 `default_tool_policy`（默认 `MCPToolPolicy()`，即旧行为不变），供运行期登记的 Server 传入更保守的策略

### 修复

- `tests/test_conversation_metrics.py` 的耗时断言不再假设 `asyncio.sleep(.01)` 等于 10ms 墙钟：Windows 上 asyncio 的定时器粒度粗于 `perf_counter`，该 sleep 实测只有约 3.7ms，让 `duration_ms >= 10` 在本地随机失败（CI 的 Linux 计时器无此偏差）。改为断言 Runner 记录的窗口**不小于模型自测耗时**——语义不变（耗时是真实测量，不是占位 0），但不再依赖绝对墙钟

### 兼容（0.14.0）

- **`ToolContext` 只新增可选字段** `tool_names`（默认 `None` = 不限制），直接构造 `ToolContext` 的旧调用方行为不变
- **`IngestionService` 的构造签名未变**（`chunker` / `embedding_provider` / `vector_store`），只是 `ingest()` 现在会校验并补齐元数据。全仓库检索确认过：该类的既有调用方为零，因此校验收紧不会影响现网代码
- **`VectorStore` 协议新增 `delete_all()`**：服务于「删除仓库即丢弃集合」。仓内只有 `ChromaVectorStore` 一个实现，第三方实现需要补这个方法
- **`MCPServerConfig` 只新增带默认值的字段**；`discover_and_register()` 新增 `dynamic` 关键字参数（默认 `False`，旧调用行为不变）
- **`ChromaVectorStore` 新增可选 `client` 参数**：多个仓库集合共用一个 `PersistentClient`，不传时自建（旧行为不变）
- **`RuntimeBundle` 新增可选字段** `knowledge` / `mcp` / `mcp_store`（默认 `None`），`app.runtime` 的既有字段一个都没动
- **注册表封板带来的行为变化**：build 之后直接调用 `registry.register()`（绕过 `HarnessApp` 门面）现在会抛 `ValueError`，此前是静默允许。门面层的 `RuntimeError` 行为未变

### 计划中

- 后续（0.14.0 起）不再新增 Harness 核心能力，建议定义为 **Open Source Release Engineering / Production Hardening（开源发布工程 / 生产加固）**：PyPI 发行流程、Dockerfile、PostgreSQL Adapter、迁移工具、生产部署指南、Benchmark 与示例应用
- 欠账与下一步见 `HANDOFF.md` 与 `AGENT.md` 第 6 节（RAG/MCP 远端连接路径缺测试、ruff/mypy 未进 CI、前端产物无一致性校验、无依赖锁文件）


## [0.13.0] - 2026-09-21

> 主题：**流式对话工作台（Streaming Workbench）**。产品定位从「可商用的多租户 Harness」收敛为**本地优先的个人 Agent 工作台**：Phase 1–12 的能力全部保留，但面向个人的运行不再套用 SaaS 配额与调用预算，前端收敛为「创建工作区 + 在工作区里对话」。
> 升级前请读 [docs/migration-v0.12-to-v0.13.md](docs/migration-v0.12-to-v0.13.md)：本版有两处**行为变化**——配额与调用预算不再拦截运行、多数环境变量改由 `harness.toml` 承载。

### 变更（工具全部抽离到应用层 `app_tools/`）

- **框架层不再内置任何业务工具**：`DesktopService` 去掉 `tools()`，只保留工作区服务能力（文件浏览、知识库存储、会话与运行记录）；`assemble_runtime()` 也不再按 `server.mode == "local"` 注册桌面工具。**修复了 `ModuleNotFoundError: No module named 'app_tools'`**——`app_tools` 不在发行版的 packages 列表里（见 `pyproject.toml`），框架层任何 `from app_tools...` 都会让 `pip install mini-harness` 之后构建运行时必然失败
- **工作区工具迁到 `app_tools/workspace.py`**：`workspace_list` / `workspace_read` / `workspace_write` / `workspace_command` / `workspace_knowledge_search`。统一按 `calculator.py` 的格式编写：Pydantic 入参模型 + 普通函数 + `tool_from_pydantic(...)`，模块底部导出 `tool_list`；副作用与审批仍由 `requires_approval=True` / `side_effect=True` 声明驱动
- **`ToolContext` 新增 `workspace_path` / `knowledge_path`**：服务端在提交 Run 时解析一次并写入上下文（同时进入 Durable 状态序列化，重跑与崩溃恢复后依然可用）。工具因此不再需要数据库或服务实例，`app_tools` 可以只依赖 harness 的契约
- **`workspace_knowledge_search` 改为读取知识库目录**：直接扫描 `knowledge_path` 下的文件做关键词检索（返回文件名与片段，自动去掉 `doc_<id>_` 上传前缀），不再查 `desktop_documents` 表。知识库路径由服务端从工作区配置读取，自定义目录同样生效
- **`app_tools/__init__.py` 汇总 `all_tools()`**：`main.py` 成为唯一定册点（`app.add_tools(all_tools())`）。`notes.py` 补上 `tool_list`，与 `calculator.py` / `workspace.py` 对齐；需要运行时依赖的 `knowledge.py`（RAG 检索管线）不进入 `all_tools()`，仍由组合根按 `[rag]` 注册
- **CLI 入口健壮性**：`load_project_app()` 先把当前目录与配置文件所在目录补进 `sys.path`（`mini-harness serve` 的 `sys.path[0]` 是 Scripts 目录，否则 `import app_tools` 会失败），并且只在「工厂模块本身找不到」时回退到零配置；模块存在但其内部 import 失败会原样抛出真实异常，不再静默退化成「一个工具都没有」
- **测试**：新增 `tests/test_app_tools.py`（工具清单与审批声明、路径越界拒绝、写入 diff、命令执行目录、知识库检索与前缀处理、缺少工作区上下文时报错）与「框架在 `app_tools` 不可导入时仍能构建运行时」的回归测试；`tests/test_desktop_api.py`、`tests/test_run_stream.py` 改为显式注册 `app_tools.workspace.tool_list`

### 新增（会话管理）

- **会话归档与恢复**：`desktop_sessions` 新增 `archived` 列（旧库启动时自动 `ALTER TABLE` 补列），`PATCH /v1/sessions/{id}` 支持 `archived` / `title`，`GET /v1/sessions?archived=true` 返回归档列表。侧栏新增「已归档 · N」折叠分组，可一键恢复。
- **会话删除**：`DELETE /v1/sessions/{id}` 按依赖倒序清理该会话的 Run 及其所有派生日志——用 `PRAGMA table_info` 找出全部带 `run_id` 的表（steps / checkpoints / events / durable_runs / 审批 / 幂等 / 计量……）后逐表删除，再删 messages、session 与 conversation，因此不会留下悬挂行。会话里还有**非终态 Run 时返回 409**，避免掏空 Worker 正在写的记录。前端为二次确认弹窗。
- **会话自动命名**：会话标题跟随第一条指令（标题仍是默认「新任务」时才覆盖），侧栏不再堆满同名条目。
- **会话隔离双保险**：服务端按 `conversation_id` 过滤，前端再按 Run 自带的 `conversationId` 核验一次——对面是没有过滤参数的旧服务时，新会话也不会串入其他会话的内容。

### 修复（工具调用气泡与实时性）

- **工具卡片更醒目**：工具卡片改为带左侧状态色条的独立气泡（执行中 / 等待批准 / 完成 / 失败 / 已跳过 用不同颜色与药丸标签），并修正同一 `call_id` 在「等待审批」与「执行完成」两个步骤被渲染成两张卡片的问题——现在合并为一张并保留最终状态；模型最后一步正文与最终输出节点内容重复渲染的问题也一并修掉。
- **事件流兜底轮询**：新增看门狗，进行中的 Run 每 2 秒对账一次服务端视图。事件流一条都没到（旧服务、代理缓冲、断线）时用服务端视图补齐文本与工具气泡，Run 进入终态后停止轮询并整体刷新；界面同时提示「实时事件流不可用，已切换为轮询同步」。此前事件流失败会直接清空进行中的 Run，导致只能靠手动刷新才看到工具调用。

### 新增（流式对话工作台）

- **模型输出改为真实流式**：`DeepSeekProvider` 改用 `AsyncOpenAI` + `stream=True`（`stream_options.include_usage`），按 `on_delta` 回调逐段下发文本；assistant 消息按分片重建 `tool_calls`，多轮工具对话仍能通过 `tool_call_id` 续接。顺带修掉「同步客户端在 async 函数里阻塞事件循环」的隐患，同一进程的 SSE 推送因此才能实时。`OpenAIProvider` 同样支持 `on_delta`（responses 流式事件 + `response.completed`）
- **进程内 Run 事件总线（`harness/streaming.py`）**：`RunEventBroker` 按 `run_id` 广播事件并保留最近 32 次 Run 的回放缓冲，`open()` 原子地返回「历史缓冲 + 实时队列」，因此「提交任务」与「打开流」之间的竞态既不丢事件也不重复。`AgentRunner` 在模型与工具转换处发出 `model.start` / `model.delta` / `model.end` / `tool.start` / `tool.end` / `phase`；`DurableAgentService` 在提交、等待审批与终态发出 `run.submitted` / `run.waiting` / `run.end`
- **SSE 端点 `GET /v1/runs/{run_id}/stream`**：每帧 `data: {json}`，连接时先整体回放缓冲再续播实时事件，15 秒心跳注释帧保活，收到 `run.end` 后服务端主动收尾；`GET /v1/runs` 新增 `conversation_id` 过滤，用于按会话重建对话历史
- **工作台前端重写为「工作区 + 对话」**：Markdown 渲染（`marked` + `DOMPurify` 消毒后注入）、模型文本逐字流式显示、工具调用卡片（工具名 / 参数 / 状态 / 返回内容 / 写入 diff，点击展开）、批准与拒绝按钮、停止运行
- **测试**：`tests/test_run_stream.py` 覆盖事件序列与 `seq` 连续性、工具结果投影、**真实 HTTP 下的增量到达**（uvicorn 实跑，同时证明模型流式不阻塞事件循环）、迟到订阅者拿到完整回放、未知 Run 返回 404；前端 `src/__tests__/workspace.spec.ts` 覆盖流式增量归并、Markdown 渲染与消毒、工具卡片、审批后同流继续

### 变更（前端简化）

- **前端从「运行控制台」收敛为单一对话界面**：删除 `TimelineView` / `RunInspector` / `RunList` / `AgentSettings` / `SystemSettings` / `WorkspaceManager` / `WorkspaceView` / 主题与布局面板 / 命令面板 / 拖拽分栏 / Toast 等约 30 个组件、store 与样式文件，只保留工作区创建（含目录浏览）、会话列表、对话流与工具调用展示
- **`harness/ui/static` 重新构建**：样式表 31.5 kB → 9.3 kB；脚本 133.6 kB → 161.5 kB（新增 Markdown 渲染与消毒依赖）
- **`.env` / `requirements` 之外的构建依赖**：`frontend/package.json` 新增 `marked` 与 `dompurify`

### 兼容（流式对话工作台）

- `AgentRunner.run` / `advance`、`DurableAgentService.submit`、`PersistentAgentService.ask` 的既有调用方式不变：`emitter` / `events` 都是可选参数，不传时行为与 0.12.0 一致
- **旧 Provider 自动降级**：`AgentRunner` 用签名探测判断 `generate()` 是否接受 `on_delta`，第三方 Provider 不实现流式也能照常运行（只是没有增量输出）
- **前端 localStorage 键变化**：由 `mini-harness.workspace.v1` 继续复用，新增 `mini-harness.session.v1`；旧布局 / 主题键不再读取
- **`DurableAgentService.submit()` 的新参数全部可选**：`workspace_id` / `workspace_path` / `knowledge_path` / `external_context` 不传时行为与 0.12 一致
- **配额相关类型仍可导入**：`QuotaService` / `QuotaDecision` / `QuotaExceededError` 与 `InMemoryRunBudgetStore` / `SQLiteRunBudgetStore` 的 `consume()` 签名都保留，接了这些类型的代码不会因为升级而 `ImportError`——只是不再产生拒绝
- **HTTP 契约不变**：Local 与 Platform 两套端点的路径、请求体与状态码未变，工作台仍然只在 `server.mode = "local"` 下挂载工作区 / 会话端点

### 变更（配额与调用预算不再拦截个人运行）

- **产品定位收敛：本地优先的个人工作台**。计量 / 账本 / 计费预览继续记录，但**不再有任何一种用量限制会拒绝一次提交**——面向个人的运行不必先配置套餐。
- **`QuotaService.check_run_submission()` 退化为兼容门面**：保留签名与 `QuotaDecision` 形状，恒返回 `allowed=True` / `code="UNLIMITED"`；`CommercialPlatformService.submit_run()` 不再做配额判定，`QuotaExceededError` 保留定义但不再抛出
- **调用预算移除**：`SecurityConfig.max_tool_calls_per_run` 默认由 `16` 改为 `None`，`DefaultToolPolicy` 不再返回 `SEC_TOOL_BUDGET_EXCEEDED`；`InMemoryRunBudgetStore` 与 `SQLiteRunBudgetStore` 的 `consume()` 保留原签名并恒返回 `True`（`durable_run_budget_calls` 表不再写入）。`HARNESS_MAX_TOOL_CALLS_PER_RUN` 已不再被读取
- **仍然生效的安全与计量能力**：禁用清单（`[security].disabled_tools`）、副作用显式审批、输入 / 输出 Guard、JSONL 审计、Usage Ledger / Reconciler / Billing Preview / Plan Snapshot 全部照旧
- **测试**：`test_monthly_token_quota_blocks_new_run` 改为 `test_monthly_usage_does_not_limit_personal_run_submission`（断言 `UNLIMITED`）；`tests/test_desktop_api.py` 新增 `test_legacy_step_and_tool_budgets_do_not_limit_personal_runs`

### 变更（Durable 暂停 / 恢复与指令注入）

- **暂停的运行会被 Worker 真正停住**：Claim 查询额外拾取 `status='waiting' AND cancel_requested=1`；Worker 每段推进前调用 `desktop.apply_instructions(state)` 并检查暂停标志，暂停时释放 Lease 回到 `pending`。释放 Lease 后会再确认一次暂停状态——否则「恢复」与「暂停」之间的竞态会让刚放下的 Run 立刻被重新 Claim 却仍然暂停
- **`AgentExecutionState` 新增 `transition_data` / `applied_instructions`**：前者记录每段推进的耗时（`duration`，毫秒），后者记录已注入的附加指令；两者都进入 Durable 序列化，因此崩溃恢复与重跑之后不会重复注入同一条指令
- **提交即落 step 0 checkpoint**：`DurableAgentService.submit()` 在入队前写入一条 `step_sequence=0` 的检查点，`/v1/runs/{run_id}/replay` 因此总能找到重跑起点
- **`DurableAgentService.submit()` 新增 `workspace_id` / `workspace_path` / `knowledge_path` / `external_context`**：工作区目录与知识库目录随 Run 一起进入 Durable 状态，工具在重跑与恢复后仍能取到同一条路径

### 修复（文档、配置来源与 0.13 语义对齐）

- **CI 从第一次运行起就全红：`pytest -q` 无法 import `app_tools` 与 `tests`**。`packages.find` 有意把 `app_tools*` / `tests*` 排除在发行版之外，而仓库既没有 `tests/__init__.py` 也没有根 `conftest.py`，于是只有「`python -m pytest`（把 cwd 加进 `sys.path`）」才跑得通；CI 用的是控制台脚本 `pytest`，9 个测试模块在 collection 阶段直接 `ModuleNotFoundError`。现补 `[tool.pytest.ini_options] pythonpath = ["."]`，并把 `tests/` 声明为常规包（避免被 site-packages 里同名的顶层 `tests` 抢占）。**两种调用方式从此一致**——这类「本地全绿、CI 全红」的偏差本身就是缺陷

- **`scripts/platform_smoke_test.py` 仍在断言「配额会拒绝提交」**：0.13 把 `QuotaService` 改成恒 `UNLIMITED` 之后，该断言必然失败（`python -m scripts.platform_smoke_test` 以退出码 1 结束）。现改为断言「允许提交 + `UNLIMITED`」，账本与计费预览的校验保持不变
- **硬编码的版本号散落在三处**：`harness/app/server.py` 的 FastAPI `version` 与 `GET /healthz` 都写死 `"0.12.0"`（README 明确把该端点写成健康检查的一部分，却会一直返回旧版本），`ObservabilityConfig.service_version` 默认 `"0.11.0"`，`frontend/package.json` 与 lockfile 停在 `0.11.0`。现分别改为 `harness.__version__`（server 与 observability）与 `0.13.0`（前端包），版本号从此只有一个来源
- **README 与 `.env.example` 曾把大量已被 `harness.toml` 取代的环境变量写成「仍然生效」**。实际只有 Provider 凭据（`DEEPSEEK_*` / `OPENAI_*` / `DASHSCOPE_*`）、`HARNESS_API_KEY_PEPPER` 与 `HARNESS_APP` 会被直接读取；其余设置一律来自 `harness.toml`，需要环境变量时请在 TOML 里写 `${VAR}` / `${VAR:-default}`。`.env.example` 已按此重写，删去 `HARNESS_MAX_INPUT_CHARS` / `OTEL_MODE` / `DEMO_MCP_URL` 等已不生效的条目
- **README 的 Provider 调用点仍写着 `main.py build_runtime()`**：0.12 起 `main.py` 只有 13 行，组装在 `harness/app/assembly.py`，已更正
- **`docs/plugins.md` 的测试路径写成 `harness/tests/...`**，实际是 `tests/test_app_config_plugins.py`

## [0.12.0] - 2026-09-20

### 新增（Open-Source DX & Backend Redesign）

- **开发者门面 `HarnessApp`（`harness/app/application.py`）**：普通开发者只需要「配置 + Tool + Plugin」三件事，`app.tool` / `app.add_tool` / `app.use` / `app.build` / `app.ask` / `app.submit` / `app.get_run` / `app.approve` / `app.cancel` / `app.chat` / `app.create_http_app` / `app.cli`。`app.runtime` 是高级逃生口，`Registry` / `Store` / `Manager` / `UnitOfWork` / `DurableWorker` 一个都没删除，只是不再要求手工组装
- **内部组合根（`harness/app/assembly.py`）**：Observability / Database / 四个 Durable Store / Security / Registry / RAG / MCP / ContextBuilder / Provider / ToolExecutor / AgentRunner / PersistentAgentService / DurableAgentService / DurableWorkerPool / 可选 Platform，全部收敛到 `assemble_runtime()`。原先散落在 `main.py` 的 1300+ 行组装逻辑整体迁入
- **函数式 Tool 注册（`harness/app/tooling.py`）**：`to_tool()` 把普通带类型注解的函数转成内部 `Tool`（`inspect.signature` + `get_type_hints` → `pydantic.create_model(extra="forbid")` → `tool_from_pydantic`）。`@tool` / `@app.tool` 装饰器**返回原函数**，因此 Tool 逻辑可以直接单元测试。旧 `Tool` 对象与 `tool_list` 继续兼容，`app.add_tools` 会自动展开可迭代集合
- **声明式配置（`harness/app/config.py`）**：`HarnessConfig` 十个分节（app / context / security / durable / observability / rag / mcp / plugins / server / platform）+ `load_config()`。支持 `${VAR}` 与 `${VAR:-default}` 展开；`harness.toml` **可选**，缺失即零配置启动
- **Entry Point 插件（`harness/app/plugins.py`）**：`HarnessPlugin` 协议只需 `register(app)`；组名 `mini_harness.plugins`，`app.use(plugin)` 显式注册，`app.discover_plugins()` 按名发现。**默认不自动发现**——安装一个包不应等于执行它的代码
- **可选依赖 Extras**：Core 收窄到 `openai` / `pydantic` / `python-dotenv` / `jsonschema` / `opentelemetry-api`；`[rag]` / `[mcp]` / `[observability]` / `[server]` / `[all]` / `[dev]` 按需安装
- **Local-first HTTP Server（`harness/app/server.py`）**：`server.mode = "local"` 提供 `/healthz` 与 `/v1/runs`（提交 / 查询 / 审批 / 取消），由 Lifespan 托管 Durable Worker Pool；`server.mode = "platform"` 复用 Phase 11 Platform API
- **Noop 层（`harness/app/noop.py`）**：关闭可选能力时 `NoopObservability` / `NoopMetrics` / `NoopSecurityService` 保持接口形状，内核因此没有 `if enabled:` 分支
- **可执行错误（`harness/app/errors.py`）**：`FeatureDependencyError` 附带安装命令，`UnsafeServerConfigurationError` 阻止无认证 Local Server 绑定公网
- **CLI（`harness/cli.py` + console_scripts）**：`mini-harness` 提供 `chat`（默认 Durable，`--immediate` 切 Immediate）/ `serve` / `doctor` / `plugins` / `security-check` / `durable-check` / `eval` / `platform-init`；`HARNESS_APP` 环境变量或 `main:app` 工厂定位项目应用
- **`harness/app/checks.py`**：`run_security_check()` 与 `run_durable_check()` 移入包内（原先在 `main.py`），脚本与 CLI 共用同一实现
- **内置 RAG Tool（`harness/app/features.py`）**：`build_rag_tool()` 让 Core 自带知识检索工具，不再依赖示例目录 `app_tools`
- **仓库工程面**：`.github/workflows/ci.yml`（Install → Compile → Test → Build，Python 3.12/3.13）、`SECURITY.md`（信任边界与漏洞报告）、`docs/architecture.md`、`docs/migration-v0.11-to-v0.12.md`、`docs/plugins.md`、`examples/quickstart.py`、`examples/plugin_example.py`、`harness.toml`
- **测试**：`tests/test_public_app.py`（装饰器保留原函数、Tool 注册冻结、Local HTTP）、`tests/test_app_config_plugins.py`（TOML `${VAR}` 展开、零配置、插件注册、loopback 保护）

### 变更（Open-Source DX & Backend Redesign）

- **`main.py` 从 1300+ 行缩到 11 行**：只做「加载配置 → 注册项目工具 → `app.cli()`」
- **默认子命令由 `api` 变为 `chat`**：开源开发者第一次运行应该是本地对话，需要 HTTP 服务时显式 `serve`。Phase 11 的 Platform 入口降为可选扩展（`[platform].enabled = true`）
- **默认模型 Provider 显式化为 DeepSeek**：`[app].provider` 默认 `"deepseek"`，`model` 不写时读 `DEEPSEEK_MODEL`；`provider = "openai"` 时走 `OpenAIProvider`（读 `OPENAI_*`）。两份实现都保留，组合根只是不再默认选择 OpenAI
- **Embedding 固定使用 Qwen**：`[rag].enabled = true` 时组合根选择 `QwenEmbeddingProvider`（DashScope OpenAI 兼容模式，读 `DASHSCOPE_*`），`OpenAIEmbeddingProvider` 保留为可显式构造的实现。**RAG 因此不再需要 `OPENAI_API_KEY`**
- **LLM Judge 默认 DeepSeek**：`mini-harness eval` 默认 `--judge-provider deepseek`，`--judge-provider openai` 保留切换能力
- **`doctor` 按 Provider 检查环境变量**：默认检查 `DEEPSEEK_MODEL` / `DEEPSEEK_API_KEY`，启用 RAG 时额外要求 `DASHSCOPE_API_KEY`，`provider = "openai"` 时改查 `OPENAI_*`
- **`harness/__init__.py` 定义公共 API**：只导出 `HarnessApp` / `HarnessConfig` / `HarnessPlugin` / `Tool` / `ToolContext` / `load_config` / `tool` 七个稳定符号；并在包入口加载 `.env`（不覆盖真实环境变量），避免 Phase 10 那类「`.env` 静默失效」问题
- **`pyproject.toml`**：版本 0.12.0、`license-files`、classifiers、Extras 拆分、`[project.scripts] mini-harness = "harness.cli:main"`、`packages.find` 只包含 `harness*`
- **`harness/security` 导出 `ProcessIsolationSandbox`** 等三个符号（原先只能从 `harness.security.sandbox` 子模块导入）

### 修复（Open-Source DX & Backend Redesign）

- **`harness/app/server.py` 的请求体模型被当成查询参数**：`SubmitRunRequest` 作为单一 Pydantic 参数时 FastAPI 默认按 query 解析，`POST /v1/runs` 返回 422 `loc=["query","body"]`；现显式标注 `Body(...)`
- **延迟导入的 `BaseModel` 让请求体模型无法解析**：在函数内 `from pydantic import BaseModel` 会让字符串注解变成未解析的 `ForwardRef`，路由注册时抛 `PydanticUserError: not fully defined`；现把 `SubmitRunRequest` 提升到模块级定义（pydantic 属于 Core 依赖，不会把 FastAPI 变成硬依赖）
- **隐藏的可选依赖泄漏**：`harness/retrieval/chroma_store.py` 在模块级 `import chromadb`，而原先只有它在 try 块内，缺 `[rag]` 时抛裸 `ImportError` 而非 `FeatureDependencyError`；现连同 `embeddings` / `projector` / `retriever` 一起放进 try，保证提示里带上安装命令。`_build_observability` 同样处理
- **`RuntimeBundle` 的可变赋值**：`RuntimeBundle` 是普通（非 frozen）dataclass，`bundle.platform = ...` 直接赋值即可，不需要 `object.__setattr__`
- **`app.chat` 与 `doctor` 对缺省子参数的假定**：`run_cli(["chat"])` 不带 `--immediate` 时 `args.immediate` 不存在；改用 `getattr(args, "immediate", False)`

### 兼容（Open-Source DX & Backend Redesign）

- **Phase 1–11 模块与构造签名零改动**：`PersistentAgentService`、`DurableAgentService`、`AgentRunner.run` / `advance`、`ToolExecutor`、`SecurityService`、`EvaluationRunner`、`CommercialPlatformService` 全部原样保留
- **旧 `Tool` 与 `tool_list` 继续可用**：`app.add_tools(tool_list)` 自动展开
- **`scripts/security_smoke_test.py` 改为从 `harness.app.checks` 导入**（原实现依赖 `main.py` 内部函数）
- **环境变量继续生效**：`HARNESS_*` / `OTEL_*` / `MAX_*` 仍被各子系统直接读取，与 `harness.toml` 共存
- **Phase 11 Platform 是可选扩展**：`sqlite` + `SQLitePlatformStore` 代码不变，只是不再默认启动

### 新增（图形工作台）

- **图形工作台（`harness/ui`）**：Codex 风格多窗体界面，支持边缘拖拽和键盘调整比例、布局记忆、响应式导航、深浅主题、任务搜索、草稿和对话保存、项目快照上下文、Markdown 导出。
- **同源 API 连接**：FastAPI 首页提供工作台，`/ui` 提供打包静态资源；前端接入现有身份校验与任务提交、轮询、审批、取消和断线后恢复查询，API Key 仅存页面内存。
- **独立演示**：`python -m harness.ui` 使用 Python 标准库启动本地界面预览；预设响应和模拟审批明确区分于真实模型执行，无新增运行依赖。

### 变更（工作台前端：Vue 3 重构）

- **前端整体重构为 Vue 3 + TypeScript + Vite + Pinia**：原 767 行单文件 `app.js`（`innerHTML` 直写 DOM、状态与视图强耦合）拆分为 25 个组件、6 个 store 与 2 个 composable；源码在 `frontend/`，构建产物输出到 `harness/ui/static/`（**入库**，运行时仍不需要 Node.js）。视觉 token、深色主题、响应式断点与无障碍语义（`role="separator"` + `aria-valuenow`、`role="tablist"` + 方向键、`role="log" aria-live`、原生 `<dialog>` 焦点陷阱、`prefers-reduced-motion`）逐条保留，未做视觉改版
- **状态与视图彻底分离**：`stores/workspace`（任务 / 对话 / 事件）、`stores/run`（提交 → 轮询 → 审批 / 取消 / 恢复）、`stores/connection`（身份与 Scope）、`stores/inspector`（布局与折叠）、`stores/ui`（对话框）、`stores/toast`；组件只读状态，不再直接操作 DOM
- **新增：右侧两个面板可折叠**。此前 `.workspace` 是写死的五列 grid，折叠态在 CSS 中并不存在；现在「上下文 · 工具」与「运行记录」各自可折叠（标题栏按钮、`Ctrl/Cmd B`、`Ctrl/Cmd J`、命令面板四种入口）。折叠后面板不消失，而是收成 38px 竖轨（图标 + 标题 + 计数），点击原位展开并恢复折叠前比例；两个面板都折叠时整列只占 38px，空间全部让给对话；仅剩一个面板展开时高度分割条自动隐藏，避免无意义的拖拽目标。折叠状态与宽高比例写入同一条 `layout` 持久化记录，并在 900px 及以下禁用（移动端由底部导航切换视图，不叠加第二套交互）
- **新增：`Ctrl/Cmd B` / `Ctrl/Cmd J` 快捷键**：全局快捷键集中到 `composables/useShortcuts`，命令面板同步暴露「折叠 / 展开」命令

### 修复（工作台前端）

- **刷新后运行卡在「运行中」**：`task.runId` 虽然落盘，但内存中的运行控制器不会恢复，此前需要用户自己发现并点击「恢复状态查询」；现在加载时对仍持有运行编号的任务自动对账并恢复轮询
- **运行记录在首轮即终止时丢失终态事件**：原实现只在状态「发生变化」时记录事件，若首次查询就返回 `completed` / `failed`，终态事件永远不会写入；现在先建立基线再比较
- **运行记录上限裁剪方向错误**：原 `events.slice(-60)` 在超过 60 条时丢弃的是**最新**事件；现改为保留最近 60 条、丢弃最旧的
- **`harness/ui/static/icon.svg` 会被构建删除**：该文件未入库且位于 `vite build` 的 `emptyOutDir` 目标目录中，首次构建即丢失；现迁移为 `frontend/public/icon.svg` 源资产并随构建输出

## [0.11.0] - 2026-09-20

### 新增

- **P11 Commercial Platform（`harness/platform`）**：`CommercialPlatformService`（Control Plane，包裹 Durable Runtime 而不侵入）、`SQLitePlatformStore`（Tenant / Plan / API Key / Usage Ledger / Run Account / Platform Audit）、`ApiKeyManager`（高熵 Key + 数据库只存 HMAC 摘要 + Scope + 撤销）、`QuotaService`（并发 Run / 每日 Run / 月 Token / 月 Tool Call）、`UsageReconciler`（从 Durable Run 的真实 `RunEvidence` 异步幂等计量）、`BillingService`（Plan Snapshot 冻结 + 整数 micro-USD + Decimal）、`create_app`（FastAPI HTTP Surface）
- **平台模型与错误（`harness/platform/models.py` / `errors.py`）**：`Tenant` / `TenantStatus` / `Plan` / `PlanLimits` / `MeterRate` / `ApiKeyRecord` / `ApiKeyStatus` / `Principal` / `UsageMetric` / `BillingPreview`；`PlatformError` 体系映射为 RFC 9457 `application/problem+json`
- **平台存储 Schema（`harness/platform/schema.py`）**：`platform_plans` / `platform_tenants` / `platform_api_keys` / `platform_usage_events` / `platform_run_accounts` / `platform_audit_events`，与 Phase 4 Repository 共用 SQLite Adapter 但领域边界独立
- **FastAPI HTTP Surface（`harness/platform/api.py`）**：`APIKeyHeader` 提取 Key → `Principal` → Tenant ACTIVE → Scope 校验；`/healthz`、`/v1/me`、`/v1/runs`（提交 / 查询 / 审批 / 取消）、`/v1/usage`、`/v1/billing/preview`、`/v1/admin/*`（套餐查看、租户列表与创建、发行 API Key、暂停租户、切换套餐）；对象级授权越权访问返回 **404**（不泄露对象存在性，OWASP API1 BOLA）；每个请求携带 `request_id`
- **FastAPI Lifespan（`harness/platform/runtime.py` / `bootstrap.py`）**：API 进程启动时托管 Durable Worker Pool + Usage Reconciler，随进程生命周期启停；`CommercialRuntime` 聚合 `core` / `store` / `api_keys` / `service` / `metering` / `billing`；`default_plans()` / `seed_default_plans()` 提供 `starter_v1` / `pro_v1` / `operator_v1` 教学套餐
- **平台指标（`harness/observability/metrics.py`）**：新增 `platform_auth_failures` / `platform_quota_denials` / `platform_usage_events`（既有 19 个指标全部保留）
- **CLI 子命令（`main.py`）**：`api`（新的默认入口）、`platform-init`（初始化套餐 / 租户并发行首批 API Key）、`platform-check`（无模型验收）
- **平台冒烟脚本（`scripts/platform_smoke_test.py`）**：不需要模型即可验证 Platform Schema / API Key 发行与认证 / Tenant / Plan / Quota / Usage / Billing Preview
- **`.env.example`**：不含任何真实密钥的环境变量示例（对话模型 / DashScope 向量模型 / OTel / 安全 / Durable / 商业平台）
- **测试**：`tests/test_platform_auth_quota.py`、`tests/test_platform_tenant_isolation.py`、`tests/test_platform_metering.py`、`tests/test_platform_api.py`
- **Provider 同构化（DeepSeek / Qwen 成为一等实现）**：新增 `DeepSeekJudgeEvaluator`（chat 接口 + `json_object` 输出），与 `OpenAIJudgeEvaluator` 共用同一套 Prompt 与评分契约（`score` 0–1 + `reason`）；`main.py eval` 新增 `--judge-provider {deepseek,openai}`（默认 `deepseek`）。模型、Judge、向量三对实现的构造参数已对齐（`model` / `api_key` / `base_url` / `batch_size`），可零参构造后直接互换

### 变更

- **默认 CLI 入口有意变化**：`python main.py` 由 `durable-chat` 变为 `api`（Phase 11 起最新产品入口是商业平台 API）；Phase 1–10 的 `durable-chat` / `chat` / `durable-check` / `security-check` / `eval` 全部保留，`durable-chat` 为兼容替代
- **`RuntimeComponents` 只做加法修改**：新增 `database` 与 `durable_store` 两个字段，使 Commercial Composition Root 复用同一个 Durable Store；原有字段全部保留
- **`pyproject.toml`**：版本升至 `0.11.0`，新增 `fastapi>=0.141.1,<1`、`uvicorn[standard]>=0.52.0,<1`（只属于最外层 HTTP Transport，不反向进入 Harness Kernel）、dev 依赖补 `httpx>=0.28,<1`
- **实际调用点全部切换到 DeepSeek / Qwen**：对话模型 → `DeepSeekProvider`（读 `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL`）、LLM Judge → `DeepSeekJudgeEvaluator`、向量模型 → `QwenEmbeddingProvider`（读 `DASHSCOPE_*`）。OpenAI 的三份实现（`OpenAIProvider` / `OpenAIJudgeEvaluator` / `OpenAIEmbeddingProvider`）**完整保留**，可通过显式参数或 `--judge-provider openai` 切回。本阶段**未新增任何 `.env` 变量**
- **基线整合（本仓库特有）**：Phase 11 代码落地时保留了 Phase 10 基线的既有实现，未按教程文档的 OpenAI 基线替换 —— `DeepSeekProvider`、`QwenEmbeddingProvider`、`load_dotenv()`、`shutdown_observability()`、`app_tools.calculator.tool_list` 注册循环、`harness.security.sandbox` 子模块导入全部保留；`python-dotenv` 依赖同步保留（教程文档的依赖清单遗漏了它）

### 修复

- **`harness/providers/openai_provider.py` 三处致命缺陷**（此前属于「接口保留了但完全不可用」）：
  - `perf_counter` / `started` 未定义（ruff F821）→ 任何成功的 Responses 调用都会 `NameError`；现补 `from time import perf_counter` 并在下发请求前取样
  - 在同步 `OpenAI` 客户端上 `await self.client.responses.create(...)` → `TypeError`；现改用 `AsyncOpenAI`
  - `self.metrics` 无条件解引用，而构造函数默认 `metrics=None` → `AttributeError`；现与 `DeepSeekProvider` 一致加 `if self.metrics is not None` 保护
- **`harness/evaluation/judge.py` Judge 输出无兜底**：`json.loads` 失败会中断整轮评测（`EvaluationRunner.run` 没有 per-case 异常隔离）；现统一走 `_parse_score()`，解析失败返回 0 分并在 `reason` 中说明，越界分数收敛到 [0, 1]
- `OpenAIJudgeEvaluator` / `OpenAIEmbeddingProvider` 补齐 `api_key` / `base_url` 显式参数，使其与对应的 DeepSeek / Qwen 实现构造签名一致

### 兼容

- **Phase 1–10 Runtime 接口没有删除**：`PersistentAgentService`、`DurableAgentService`、`AgentRunner.run` / `advance`、`ToolExecutor`、Security、Evaluation 全部原样保留，Platform 只包裹
- **`HARNESS_API_KEY_PEPPER` 只在 Commercial Runtime 强制**：`durable-chat` / `chat` / `durable-check` / `security-check` / `eval` 不依赖 Platform API Key
- **依赖方向固定**：`FastAPI / CLI → ApiKeyManager → Principal → CommercialPlatformService → DurableAgentService → Phase 1–10 Runtime`；`AgentRunner` 本阶段未做任何修改，没有增加 `tenant` / pricing / API key / billing 分支
- **客户端不提交权限**：`POST /v1/runs` 只接受 `input`；Tenant 由 API Key 解析，Tool Permission 由 `Plan.tool_permissions` 决定，让套餐 Entitlement 成为服务端事实
- **Billing Provider 可插拔**：当前为内部 Usage Ledger → `BillingService` Preview，未来经 `BillingExporter` 接入 Stripe / ERP / 自建计费，不影响 Agent Runtime

### 已知边界

- SQLite 仍是单节点事实源：`PlatformStore` 与 `DurableStore` 共用同一个 SQLite 文件，适用于本地优先产品 / 单节点 SaaS MVP / 小团队内部服务 / 教学与 Preview；正式多节点部署应迁移 PostgreSQL
- 尚无严格的分布式 HTTP Rate Limiter；Token Quota 为「完成后计量 + 下次请求阻止」；Usage Ledger 与 Durable Submit 之间不是跨领域原子事务（靠稳定 `event_key` + 对账消除重复，支付级系统应使用 Transactional Outbox）
- Billing 目前为 Preview / 内部账本计算，尚未实现 Tax / Invoice Finalization / Refund / Credit Note / Payment Collection / Stripe Webhook
- API Key 是第一版 M2M Auth；Admin Control Plane API 已完成，但没有品牌化 Dashboard UI（开发期使用 `/docs`）

## [0.10.0] - 2026-09-20

### 新增

- **P10 Durable Execution（`harness/durable`）**：`DurableAgentService`（提交 Run 并驱动状态机）、`DurableWorker` / `DurableWorkerPool`（`asyncio.TaskGroup` 结构化并发 + Lease 心跳）、`SQLiteDurableStore`（Queue / Claim / Lease / 乐观版本 / 取消）、`SQLiteApprovalStore`（持久审批，跨进程恢复）、`SQLiteRunBudgetStore`（按 call_id 去重的持久预算）、`SQLiteIdempotencyStore`、`AgentExecutionState` 序列化（`serialization.py`）与跨 Worker Trace 传播（`tracing.py`）
- **Durable 状态模型（`harness/durable/models.py`）**：`ExecutionPhase`（MODEL / TOOL / WAITING_APPROVAL / WAITING_RECONCILIATION / COMPLETED / FAILED / CANCELLED）、`DurableRunStatus`、`AgentExecutionState`、`DurableRunRecord` / `DurableSubmission` / `DurableResult`、`DurableConflictError` / `DurableLeaseLostError`
- **Durable 配置（`harness/durable/config.py`）**：`DurableConfig`（worker_count / lease_seconds / poll_interval / idle_backoff / transition_retry_delay / max_transitions_per_claim）
- **幂等与对账（`harness/tools/idempotency.py`）**：`IdempotencyStatus`（`STARTED` / `COMPLETED` / `UNCERTAIN`）、`IdempotencyRecord`、`IdempotencyStore` Protocol
- **P9 安全补全（`harness/security/sandbox.py`）**：`ProcessIsolationSandbox`（`shell=False`、可执行文件 allowlist、最小环境变量、临时工作目录、超时与输出上限）、`SandboxPolicyError`、`SandboxResult`；文档与代码均明确标注这是 **Process Isolation Adapter，不是强 OS 沙箱**
- **副作用示例工具（`app_tools/notes.py`）**：`create_note`（写本地 JSONL，`side_effect=True`，权限 `note.create`），用于端到端验证 Approval Gate
- **可观测性 `file` 导出模式**：`OTEL_MODE=file` 时 span 与指标写入 `OTEL_TELEMETRY_PATH`（默认 `data/telemetry.log`）、结构化 JSON 日志写入 `OTEL_LOG_PATH`（默认 `data/logs.jsonl`），控制台只保留对话与工具输出；落盘文件固定 UTF-8，避免中文 Windows 下 console exporter 继承 gbk 造成的乱码
- **`shutdown_observability()`**：进程退出时（含质量门失败等异常路径）`force_flush` 并关闭 Tracer / Meter Provider，避免最后一批 span 与指标丢失
- **测试**：`tests/test_durable_execution.py`、`tests/test_durable_store.py`、`tests/test_idempotency.py`、`tests/test_sandbox.py`；`scripts/security_smoke_test.py`

### 变更

- **`main.py` 入口重构**：新增 `durable-chat`（默认）/ `durable-check` 子命令，保留 `chat` / `security-check` / `eval`；Composition Root 组装 Durable Store、Security、Idempotency 与 Worker Pool
- **`AgentRunner` 支持分段推进**：保留即时 `run()`，新增 `create_execution()` / `advance()`，使同一条模型—工具循环可由不同 Worker 分步执行与恢复
- **`ToolExecutor` 恢复 Phase 2 Middleware 扩展点**（`harness/tools/middleware.py`），并接入 Security 策略与 Idempotency
- **`ContextBuilder` 恢复 `ContextPolicy` 与 `sources`**（`harness/context/policy.py` / `sources.py`），上下文选择策略与组装机制分离
- **`pyproject.toml`**：版本升至 `0.10.0`、`requires-python >=3.11`、补 `[build-system]`、新增 `ruff` / `mypy` 配置与 `asyncio_mode = "auto"`、补回 `python-dotenv` 依赖
- **`QwenEmbeddingProvider` 恢复并适配**：DashScope OpenAI 兼容模式，零参构造读取 `DASHSCOPE_*`，`base_url` 支持回退兼容模式默认地址，移除调试用 `print`

### 修复

- **Canonical Baseline Repair（Phase 1–9 基线修复）**：恢复被后续精简示例误删的能力 —— `ToolMiddleware`、`ContextPolicy` / `sources`、`Step` / `RuntimeEvent` 与完整 SQLite Schema、完整 MCP 网关与可选服务器降级逻辑、`OpenAIEmbeddingProvider`、带 Observability 的 `RetrievalPipeline`
- **评估链路缺陷修正**：`ForbiddenToolEvaluator` 判定反转（原实现 `missing = forbidden_used - actual` 恒为空集，导致「禁止工具」检查永远通过）；`DatasetFromatError` 拼写修正为 `DatasetFormatError`；`ApplicationResult` 补回 `evidence` 回传（评估器此前拿不到工具执行事实）；Runner 累加模型用量（`state.evidence.model_usage + model_result.usage`）
- `main.py` 缺少 `load_dotenv()`，导致 `.env`（模型 / MCP / 安全 / 可观测性配置）完全不生效
- 遥测未 `force_flush`，进程退出时最后一批 span 与指标丢失
- `main.py` 与基线不一致的两处引用：`app_tools.calculator` 实际导出为 `tool_list`（改为 `for` 循环注册）、`ProcessIsolationSandbox` 需从 `harness.security.sandbox` 直接导入

## [0.9.0] - 2026-09-20

### 新增

- **P9 Security（`harness/security`）**：`SecurityService`（输入 / 输出检查与运行收尾）、Guard 集合（`InputLengthGuard` / `OutputLengthGuard` / `PromptInjectionSignalGuard` / `SecretOutputGuard`）、`DefaultToolPolicy`（禁用清单 → 调用预算 → 副作用 / 显式审批的确定性判定）、`InMemoryApprovalStore` / `InMemoryRunBudgetStore`、`JsonlAuditSink` / `NullAuditSink` 审计、`SecurityConfig` 与 `SecurityAction` / `SecurityDecision` / `SecurityFinding` / `SecuritySeverity` 模型
- **`security-check` 子命令**：无需网络的 Phase 9 验收，覆盖"未审批副作用工具 → APPROVAL_REQUIRED → 审批后 SUCCESS / Prompt Injection 信号 / Secret 脱敏 / 允许的可执行文件"
- **测试**：`tests/test_security.py`、`tests/test_security_evaluation.py`、`tests/test_security_tool_result.py`、`tests/fakes_security.py`

### 变更

- `ToolExecutor` 在执行前加入确定性安全策略关卡；`Tool` 新增 `requires_approval` 字段（即使 `side_effect=False` 也可要求审批）
- `PersistentAgentService` 接入 `SecurityService`：运行前后做输入 / 输出检查，安全决策写入 `RunEvidence.security_decisions` 并落审计

## [0.8.0] - 2026-09-18

### 新增

- **P8 评估（`harness/evaluation`）**：`EvaluationRunner` 评测编排（`evaluation.run` / `evaluation.case` span 与 case 计数、耗时指标）、JSONL 数据集加载与格式校验（`load_jsonl_dataset` / `DatasetFormatError`，校验非空 id、id 不重复、非空 input）、确定性评估器（`AnswerContainsEvaluator` / `RequiredToolEvaluator` / `ForbiddenToolEvaluator` / `MaxStepsEvaluator`）、可选 `OpenAIJudgeEvaluator`（参考答案 / 评分标准，结构化 JSON Schema 输出 + 阈值判定）、JSON 报告落盘（`write_json_report`）、质量门（`assert_quality_gate` / `EvaluationGateError`）、评测目标适配器 `HarnessEvaluationTarget`
- **评测数据模型（`harness/evaluation/models.py`）**：`EvalCase` / `EvalSample` / `EvalScore` / `EvalCaseResult` / `EvalSummary` / `EvalRunResult`
- **评估事实通道（`harness/models.py`）**：新增 `RunEvidence` 与 `ToolExecutionRecord`，Runner 逐层回传工具执行记录与模型用量，评估器不再依赖 Telemetry Backend
- **CLI 子命令（`main.py`）**：`chat`（默认，保持 Phase 7 兼容）与 `eval`；`eval` 支持 `--dataset` / `--suite` / `--report` / `--min-pass-rate` / `--min-average-score` / `--judge-model`，质量门未通过时以非零退出码结束
- **脚本与数据**：`scripts/evaluation_smoke_test.py`（不依赖真实模型的评测冒烟）、`scripts/compare_eval_reports.py`（与基线报告做回归对比）、`evals/datasets/smoke.jsonl`（本地工具 / MCP 工具 / 无工具三个场景）、`evals/reports/baseline.json`（回归基线）
- **测试**：`tests/test_evaluation.py` 与 `tests/fakes_evaluation.py`
- **指标**：`HarnessMetrics` 新增 `eval_cases` / `eval_case_duration`，并为既有指标补充 description 与 unit

### 变更

- `PersistentAgentService.ask` 回传 `RunEvidence`；`ApplicationResult` 新增 `evidence` 字段
- Checkpoint 的 `working_state` 改用 `dataclasses.asdict` 序列化
- `AgentRunner` 采集 `ToolExecutionRecord`（call_id / name / arguments / status / error_code）与 `ModelUsage`
- `tests/fakes_observability.py` 扩展 FakeMetrics（补充评估指标桩）
- README 更新至 Phase 1–8：路线图、能力表、`eval` 使用说明、项目结构与设计要点

### 修复

- `harness/application.py` 缺少 `field` / `asdict` 导入，导致模块导入即 `NameError`
- `harness/runner.py` 工具证据处引用了未定义的 `tool_result`（应为 `result`），任何工具调用都会 `NameError`
- `harness/application.py` 指标名拼写 `agnet_runs` → `agent_runs`
- `harness/observability/collector-cofig.yaml` 文件名拼写 → `collector-config.yaml`
- `main.py` MCP 默认地址 `localhost` → `127.0.0.1`：演示服务器只监听 IPv4 回环地址，使用 `localhost` 时客户端可能解析到 `::1` 导致工具发现失败，且可选服务器会静默降级

## [0.7.0] - 2026-09-18

### 新增

- **P7 可观测性（`harness/observability`）**：OTel 引导 `configure_observability`（TracerProvider + MeterProvider，Console / OTLP 双导出，资源属性 service.name / service.version）、`Observability.span` 上下文管理器与 `SpanHandle`（受限 span 能力：属性 / 事件 / 异常 / 错误状态）、`HarnessMetrics` 指标集（agent / tool / mcp 调用与错误计数、model input / output token、agent / model / tool / retrieval / mcp 耗时直方图、检索结果数）、结构化 JSON 日志（自动注入 `trace_id` / `span_id`）、模型成本核算（`ModelPrice` / `CostCalculator`）、`ObservabilityConfig`
- **模型用量采集**：新增 `ModelUsage`（input / output / total / cached tokens）；Provider 上报 `gen_ai.*` span 属性与 token、耗时指标
- **观测接入各子系统**：`agent.loop`（Runner）、`gen_ai.generate`（Provider）、`tool.execute`（ToolExecutor）、`retrieval.search`（RetrievalPipeline）、`mcp.tool.call`（MCPGateway）、`persistence.transaction`（UnitOfWork）
- **多轮会话**：`PersistentAgentService.ask` 支持传入 `conversation_id` 续接会话（租户校验 + 历史回放 `list_recent`），返回 `ApplicationResult`（conversation_id / run_id / output / steps）
- **上下文预算回归**：`TokenBudget`（含安全边距）+ `ApproxTokenCounter` + `ContextBuilder` 历史窗口与超预算裁剪（记录 `dropped_messages`）
- **脚本与测试**：`scripts/observability_smoke_test.py`；`tests/test_observability.py` 与 `tests/fakes_observability.py`（Fake span / metrics）
- **依赖**：新增 `opentelemetry-api`、`opentelemetry-sdk`、`opentelemetry-exporter-otlp-proto-http`；`harness/observability/` 下提供 OTel Collector 参考配置

### 变更

- `main.py` 组装流程重构：遥测初始化前置，交互式循环支持多轮会话（输入 `exit` 退出）
- `ContextBuilder` 改为持有 `TokenBudget` / `ApproxTokenCounter` / `recent_message_limit`；`ModelContext` 调整为 `instructions + input_data + estimated_tokens + dropped_messages + user_input`
- `AgentRunner.run` 拆分为外层 span 包装与 `_run_loop`；`history` 参数改为必传
- 各子系统构造函数新增 `observability` / `metrics` 注入（未接入时自动退化为空实现）
- 测试目录调整：历史测试归档至 `del/tests/`，`tests/` 保留可观测性测试
- `pyproject.toml` 版本号同步为 `0.7.0`

### 修复

- `harness/observability/config.py` 误引入 `_pytest` 内部模块依赖
- `harness/persistence/repositories.py` 重复导入 `Message` / `MessageRole`

## [0.6.0] - 2026-09-16

### 新增

- **P6 MCP 集成（`harness/mcp`）**：MCP 网关（`MCPGateway`，HTTP / STDIO 双传输、分页发现、允许列表）、远程工具适配器（`adapt_mcp_tool`：远程 MCP Tool → 统一 `Tool`，权限 `mcp.{server}.{tool}`、来源与注解元数据）、发现与注册（`discover_and_register` / `MCPManager`，并发发现、必需服务器失败即抛错、可选服务器自动降级）、工具策略（`MCPToolPolicy`：副作用 / 幂等 / 审批 / 重试 / 超时）、资源读取（`read_text_resource`）、配置模型（`MCPServerConfig`）与错误体系
- **演示 MCP Server（`mcp_servers/demo_server.py`）**：`multiply` / `get_order_status` 工具与 `guide://harness` 资源
- **应用服务层（`harness/application.py`）**：`PersistentAgentService` 将会话 / 运行 / 消息落库与 AgentRunner 编排在一起，运行状态自动迁移（RUNNING → COMPLETED / FAILED）
- **工具系统 0.6.0 重写**：统一 `Tool`（`input_schema` JSON Schema 输入）、`tool_from_pydantic` 工厂（Pydantic → JSON Schema）、`validate_tool_arguments` 校验（jsonschema Draft 2020-12，拒绝外部 `$ref`）
- **脚本**：`scripts/smoke_test.py`（本地工具 + MCP 工具端到端冒烟）、`scripts/inspect_mcp_server.py`（服务器工具清单与调用检查）
- **工程化**：`pyproject.toml`（项目元数据、依赖声明、pytest 配置）；`harness` 及各子包补充 `__init__.py`

### 变更

- **上下文基线简化**：`ContextBuilder` 改为分区组装指令（系统指令 + 工作状态 + 检索知识 + 外部上下文）+ 用户输入；`ModelContext` 精简为 `instructions` / `user_input`
- **Provider 更新**：`generate` 改为异步，无参构造回退环境变量；chat 接口下 `instructions` 以首轮 system 消息注入
- **执行器简化**：移除中间件，执行流程为 查找 → JSON Schema 校验 → 权限 → 超时/重试
- **模块归档**：移除的模块统一移入 `del/` 留档（上下文预算 / 策略 / 来源、检索内存存储 / 指标 / 重排、状态机 / 检查点、工具中间件、旧版示例工具与脚本等）
- **依赖声明**：`pyproject.toml` 补充 `python-dotenv`，`requires-python` 修正为 `>=3.12`（sqlite3 `autocommit` 参数要求）
- **测试**：新增 `test_mcp_adapter` / `test_mcp_integration` / `fakes_mcp`；`test_tool_runtime` 适配 0.6.0 工具 API；共 11 个用例全部通过

### 修复

- `harness/tools/executor.py` 重复定义的 `RetryableToolError` 覆盖了导入版本，导致重试逻辑失效
- `harness/mcp/client.py` 调用异常信息引用了未定义变量（`remote_name` → `tool_name`）
- 移除 `harness/tools/definition.py` 与 `harness/context/models.py` 中误引入的 `_pytest` 内部模块依赖

## [0.5.0] - 2026-09-15

### 新增

- **P5 RAG 检索模块（`harness/retrieval`）**：文档加载（`loaders`）、字符切分含重叠与稳定 ID（`chunkers`）、嵌入提供方（`QwenEmbeddingProvider` / `OpenAIEmbeddingProvider`）、向量存储（`ChromaVectorStore` 持久化 + `InMemoryVectorStore`，均实现 `VectorStore` 协议）、摄取服务（`IngestionService`）、稠密检索（`DenseRetriever`）、检索流水线（候选召回 → 重排 → 最终结果）、证据投影（`RetrievalContextProjector`）、相似度与指标（`cosine_similarity` / `recall_at_k`）
- **知识检索工具**：`app_tools/knowledge.py` 提供 `search_knowledge_base`（支持多租户 where 过滤，返回带来源/章节/分数的证据文本）
- **上下文注入**：`ContextBuilder.build` 新增 `retrieved_context` 参数，向系统消息注入 `[RETRIEVED CONTEXT]` 段（优先级 75）
- **脚本**：`scripts/ingest_knowledge.py`（加载与切分演示）、`scripts/search_knowledge.py`（端到端检索演示）

### 变更

- 测试目录 `test/` 重命名为 `tests/`，新增 `test_chunking` / `test_retrieval` / `test_fakes`，共 18 个用例全部通过
- `.gitignore` 新增排除向量库数据目录 `data/`
- `main.py` 注册知识检索工具

## [0.4.0] - 2026-09-14

### 新增

- **P1 Harness Kernel**：`AgentRunner` 主循环、`ToolCall`/`ModelResult` 数据模型、`DeepSeekProvider`（chat 接口）与 `OpenAIProvider`（responses 接口）
- **P2 Production Tool Runtime**：工具注册表、执行器（参数校验 → 权限检查 → 中间件 → 超时/重试 → 统一结果）、中间件协议与日志实现、示例工具（计算器 / sleep / delete_file）
- **P3 Context Engineering**：TokenBudget 预算、ContextPolicy 策略、ContextBuilder 组装与裁剪、滑动窗口、WorkingState 注入、超长工具结果截断
- **P4 State / Session / Persistence**：Run / Step / Checkpoint 状态模型与状态机、SQLite schema、Repository 仓储、UnitOfWork 事务边界
- 测试：13 个 pytest 用例（工具运行时 / 上下文 / 持久化）
- 工程：`.gitignore`（排除 `.env`、`del/` 与缓存目录）

### 文档

- 标准化 README：徽章、目录导航、11 阶段路线图、贡献 / 更新日志 / 许可证章节
- 新增 MIT [LICENSE](LICENSE)、[CONTRIBUTING.md](CONTRIBUTING.md)、本更新日志
