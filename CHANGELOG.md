# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 计划中

- 主体 Harness 教程（Phase 1–11）已完成。后续不再新增 Harness 核心能力，建议定义为 **Open Source Release Engineering / Production Hardening（开源发布工程 / 生产加固）**：架构文档、Public API Review、语义化版本与发行流程、GitHub Actions、PyPI / Dockerfile、PostgreSQL Adapter、迁移工具、生产部署指南、Benchmark 与示例应用

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
