# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- Phase 9（Security）：沙箱执行、权限模型增强、审计与脱敏

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
