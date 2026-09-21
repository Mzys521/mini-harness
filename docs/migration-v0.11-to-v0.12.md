# 文件：docs/migration-v0.11-to-v0.12.md
# Migration: 0.11 → 0.12

Phase 12 不删除任何 Phase 1–11 能力，但**改了默认入口**。本页说明需要改什么。

## Before（0.11）

```python
# main.py 约 1300 行：手工组装整个 Runtime
async def build_runtime() -> RuntimeComponents:
    observability, metrics = build_observability()
    database = Database(...)
    durable_store = SQLiteDurableStore(database)
    approval_store = SQLiteApprovalStore(database)
    budget_store = SQLiteRunBudgetStore(database)
    idempotency_store = SQLiteIdempotencyStore(database)
    security = build_security(...)
    registry = ToolRegistry()
    for tool in tool_list:
        registry.register(tool)
    pipeline = RetrievalPipeline(...)
    registry.register(build_search_knowledge_tool(...))
    await mcp_manager.register_all_tools(registry)
    context_builder = ContextBuilder(...)
    provider = DeepSeekProvider(...)
    executor = ToolExecutor(...)
    runner = AgentRunner(...)
    application = PersistentAgentService(...)
    durable = DurableAgentService(...)
    worker_pool = DurableWorkerPool(...)
    return RuntimeComponents(...)
```

子命令靠 `argparse` 手工分发：`api` / `platform-init` / `platform-check` / `durable-chat` / `chat` / `durable-check` / `security-check` / `eval`。

## After（0.12）

```python
# main.py
from app_tools.calculator import add_tool, tool_list
from app_tools.notes import create_note_tool

from harness import HarnessApp

app = HarnessApp.from_toml("harness.toml", optional=True)
app.add_tools(add_tool, create_note_tool, tool_list)

if __name__ == "__main__":
    app.cli()
```

同样的组装逻辑整体搬到了 `harness/app/assembly.py`，由 `app.build()` 触发。

## 子命令对照

| 0.11 | 0.12 |
| --- | --- |
| `python main.py`（默认 `api`） | `mini-harness serve`（或 `python main.py serve`） |
| `python main.py api` | `mini-harness serve` |
| `python main.py durable-chat` | `mini-harness chat`（默认 Durable） |
| `python main.py chat` | `mini-harness chat --immediate` |
| `python main.py durable-check` | `mini-harness durable-check` |
| `python main.py security-check` | `mini-harness security-check` |
| `python main.py eval` | `mini-harness eval` |
| `python main.py platform-init` | `mini-harness platform-init` |
| `python main.py platform-check` | 已由 `platform-smoke` 脚本与 `doctor` 覆盖 |

> 默认子命令由 `api` 变为 `chat`：开源开发者的第一次运行应该是本地对话，而不是启动一个商业平台 API。需要 HTTP 服务时显式 `serve`。

## 配置对照

| 0.11 环境变量 | 0.12 |
| --- | --- |
| `HARNESS_DATABASE_PATH` | `[app].database_path`（环境变量仍可覆盖） |
| `HARNESS_WORKER_COUNT` | `[durable].worker_count` |
| `HARNESS_LEASE_SECONDS` | `[durable].lease_seconds` |
| `HARNESS_MAX_INPUT_CHARS` 等 | `[security].*` |
| `OTEL_MODE` / `OTEL_EXPORTER_OTLP_ENDPOINT` | `[observability].exporter` / `.otlp_endpoint` |
| `HARNESS_API_KEY_PEPPER` | `[platform].api_key_pepper`（环境变量仍可覆盖） |

`harness.toml` 支持 `${VAR}` 与 `${VAR:-default}` 展开，因此两种方式可以共存。

## Provider 变化

0.11 已经把实际调用点切到 DeepSeek / Qwen。0.12 把这件事写进配置：

```toml
[app]
provider = "deepseek"    # 默认
model = "deepseek-chat"  # 不写则读 DEEPSEEK_MODEL
```

- **模型**：默认 `DeepSeekProvider`；`provider = "openai"` 时走 `OpenAIProvider`（需要 `OPENAI_API_KEY` / `OPENAI_MODEL`）。两份实现都保留。
- **Embedding**：`[rag].enabled = true` 时固定使用 `QwenEmbeddingProvider`（DashScope OpenAI 兼容模式，读 `DASHSCOPE_*`）。`OpenAIEmbeddingProvider` 保留为可显式构造的实现，但组合根不会选择它，因此 RAG 不再需要 `OPENAI_API_KEY`。
- **LLM Judge**：`mini-harness eval` 默认 `--judge-provider deepseek`；`--judge-provider openai` 可切回。

`mini-harness doctor` 会按当前 provider 检查对应的环境变量。

## Compatibility

- Phase 1–11 的模块、类与构造签名**没有改动**：`PersistentAgentService`、`DurableAgentService`、`AgentRunner.run` / `advance`、`ToolExecutor`、`SecurityService`、`EvaluationRunner`、`CommercialPlatformService` 全部原样保留
- 旧 `Tool` 对象与 `tool_list` 继续可用：`app.add_tools(tool_list)` 会自动展开可迭代的 Tool 集合
- `scripts/*` 中的 `platform_smoke_test.py` / `evaluation_smoke_test.py` / `observability_smoke_test.py` / `ingest_knowledge.py` 不受影响
- `scripts/security_smoke_test.py` 改为调用 `harness.app.checks.run_security_check`（原实现从 `main.py` 导入）
- Phase 11 Platform 从「默认入口」降为可选扩展：`[platform].enabled = true` 才构建
