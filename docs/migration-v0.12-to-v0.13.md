# 文件：docs/migration-v0.12-to-v0.13.md
# Migration: 0.12 → 0.13

0.13 是**本地工作台（Streaming Workbench）**版本。功能只增不减，但有**两处行为变化**会影响到已有部署，本页说明需要改什么。

## 1. 配置只有一个来源：`harness.toml`

0.12 起配置由 `HarnessConfig` 统一承载，**子模块不再读 `HARNESS_*` / `OTEL_*` / `MAX_*`**。0.13 把文档与 `.env.example` 对齐到这一事实：以前「直接 export 一个环境变量就生效」的写法，现在多半已经无效。

仍然直接读环境变量的只有：

| 变量 | 原因 |
| --- | --- |
| `DEEPSEEK_*` / `OPENAI_*` / `DASHSCOPE_*` | 凭据 |
| `HARNESS_API_KEY_PEPPER` | 平台 HMAC Pepper，必须长期稳定 |
| `HARNESS_APP` | 决定加载哪个工厂模块，早于配置解析 |

其余变量需要在 TOML 里显式引用：

```toml
[app]
database_path = "${HARNESS_DATABASE_PATH:-data/harness.db}"
max_steps = 8

[context]
max_context_tokens = 32000
reserved_output_tokens = 4000
recent_message_limit = 20

[security]
max_input_chars = 16000
max_output_chars = 32000
detect_prompt_injection_signals = true
block_prompt_injection_signals = false
approval_required_for_side_effects = true
disabled_tools = []                 # 原来的 HARNESS_DISABLED_TOOLS（逗号分隔）现在写 TOML 数组
audit_path = "data/security_audit.jsonl"

[durable]
worker_count = 2
lease_seconds = 120
poll_interval_seconds = 0.5

[observability]
enabled = false
exporter = "console"                # console | file | otlp
otlp_endpoint = "http://localhost:4318"
log_level = "${LOG_LEVEL:-INFO}"
```

对照表（旧环境变量 → 新配置项）：

| 0.12 之前 | 0.13 |
| --- | --- |
| `HARNESS_DATABASE_PATH` | `[app].database_path`（需 `${...}` 引用才随环境变化） |
| `HARNESS_WORKER_COUNT` / `HARNESS_LEASE_SECONDS` / `HARNESS_POLL_SECONDS` | `[durable].worker_count` / `.lease_seconds` / `.poll_interval_seconds` |
| `HARNESS_MAX_INPUT_CHARS` / `HARNESS_MAX_OUTPUT_CHARS` | `[security].max_input_chars` / `.max_output_chars` |
| `HARNESS_DETECT_PROMPT_INJECTION` / `HARNESS_BLOCK_PROMPT_INJECTION` | `[security].detect_prompt_injection_signals` / `.block_prompt_injection_signals` |
| `HARNESS_APPROVAL_FOR_SIDE_EFFECTS` | `[security].approval_required_for_side_effects` |
| `HARNESS_DISABLED_TOOLS` | `[security].disabled_tools`（TOML 数组） |
| `HARNESS_SECURITY_AUDIT_PATH` | `[security].audit_path` |
| `OTEL_MODE` / `OTEL_EXPORTER_OTLP_ENDPOINT` / `LOG_LEVEL` | `[observability].exporter` / `.otlp_endpoint` / `.log_level` |
| `OTEL_TELEMETRY_PATH` / `OTEL_LOG_PATH` | **暂无 TOML 入口**：`exporter = "file"` 时固定写 `data/telemetry.log` 与 `data/logs.jsonl`；需要自定义路径请直接构造 `harness.observability.config.ObservabilityConfig` |
| `MAX_CONTEXT_TOKENS` / `RESERVED_OUTPUT_TOKENS` / `RECENT_MESSAGE_LIMIT` | `[context].max_context_tokens` / `.reserved_output_tokens` / `.recent_message_limit` |
| `HARNESS_METERING_POLL_SECONDS` / `HARNESS_USAGE_SYNC_BATCH_SIZE` | `[platform].metering_poll_seconds` / `.usage_sync_batch_size` |
| `HARNESS_MAX_TOOL_CALLS_PER_RUN` | **已移除**，见下一节 |
| `DEMO_MCP_URL` | `[mcp].servers[].url`（演示服务器地址改由 MCP 配置声明） |

`HARNESS_API_KEY_PEPPER` 仍然两种写法都支持：环境变量，或 `[platform].api_key_pepper`。

## 2. 配额与调用预算不再拦截运行

产品定位收敛为**本地优先的个人工作台**，因此不再有「用量上限拒绝一次提交」这回事。计量、账本与计费预览继续工作。

| 能力 | 0.12 | 0.13 |
| --- | --- | --- |
| `QuotaService.check_run_submission()` | 按并发 Run / 每日 Run / 月 Token / 月 Tool Call 判定 | 恒返回 `QuotaDecision(allowed=True, code="UNLIMITED")` |
| `CommercialPlatformService.submit_run()` | 配额不足抛 `QuotaExceededError` | 不做配额判定 |
| `SecurityConfig.max_tool_calls_per_run` | 默认 `16`，超出返回 `SEC_TOOL_BUDGET_EXCEEDED` | 默认 `None`，不再拦截 |
| `InMemoryRunBudgetStore` / `SQLiteRunBudgetStore.consume()` | 真正计数与限流 | 保留签名，恒返回 `True` |
| Usage Ledger / Reconciler / Billing Preview / Plan Snapshot | 记录 | **不变，继续记录** |

需要升级的调用方：

```python
# 0.12：调用方需要处理配额拒绝
try:
    await platform.submit_run(...)
except QuotaExceededError:
    ...

# 0.13：不会再有配额拒绝；QuotaExceededError 仍然可导入（兼容旧 except），只是不再被抛出
await platform.submit_run(...)
```

`QuotaService` / `QuotaDecision` / `QuotaExceededError` 都**没有被删除**，导入不会失败；只是不再产生拒绝。需要真正限流的部署请在网关层（Nginx / Envoy / API Gateway）或自建中间件实现。

## 兼容性检查清单

- **Phase 1–12 的模块与构造签名不变**：`PersistentAgentService`、`AgentRunner.run` / `advance`、`ToolExecutor`、`SecurityService`、`EvaluationRunner`、`CommercialPlatformService` 原样保留
- **`DurableAgentService.submit()` 新增的参数全部可选**：`workspace_id` / `workspace_path` / `knowledge_path` / `external_context`
- **HTTP 端点路径与状态码不变**：Local 与 Platform 两套 Surface 都保持 0.12 的形状；新增的是 Local 模式下的工作区 / 会话 / 事件流端点
- **前端 localStorage**：`mini-harness.workspace.v1` 继续复用，新增 `mini-harness.session.v1`；旧布局 / 主题键不再读取
- **`app_tools/` 现在是唯一的工具定义位置**：框架层不再内置业务工具，也不 import 该包。若你此前依赖「框架自带工作区工具」，请在项目入口注册 `app_tools.all_tools()`
