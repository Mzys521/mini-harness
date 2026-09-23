# 文件：harness/app/assembly.py
from __future__ import annotations

import os
from copy import copy
from dataclasses import replace
from typing import Iterable

from harness import __version__
from harness.app.config import HarnessConfig
from harness.app.errors import FeatureDependencyError
from harness.app.features import build_rag_tool, create_rag_write_tool
from harness.app.noop import NoopMetrics, NoopObservability, NoopSecurityService
from harness.app.personal import AutomationScheduler, PersonalCatalog, submit_local
from harness.app.personal_store import PersonalStore
from harness.app.runtime import RuntimeBundle
from harness.app.temporary_chat import TemporaryChats
from harness.application import PersistentAgentService
from harness.context.budget import ApproxTokenCounter, TokenBudget
from harness.context.builder import ContextBuilder
from harness.context.policy import ContextPolicy
from harness.durable import (
    DurableAgentService,
    DurableConfig,
    DurableWorker,
    DurableWorkerPool,
    SQLiteApprovalStore,
    SQLiteDurableStore,
    SQLiteIdempotencyStore,
    SQLiteRunBudgetStore,
)
from harness.persistence.database import Database
from harness.runner import AgentRunner
from harness.security import (
    DefaultToolPolicy,
    InputLengthGuard,
    JsonlAuditSink,
    OutputLengthGuard,
    PromptInjectionSignalGuard,
    SecretOutputGuard,
    SecurityConfig,
    SecurityService,
)
from harness.streaming import RunEventBroker
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry


def _build_observability(config: HarnessConfig):
    """Observability Extra：默认 Noop。

    observability/config.py 只依赖标准库，因此可以安全地放进 try 内一起导入；
    这样缺少 SDK 时错误信息里能带上 [observability] 的安装提示，而不是裸 ImportError。
    """
    if not config.observability.enabled:
        return NoopObservability(), NoopMetrics()
    try:
        from harness.observability.bootstrap import configure_observability
        from harness.observability.config import ObservabilityConfig
        from harness.observability.metrics import HarnessMetrics
        from harness.observability.service import Observability
    except ImportError as exc:
        raise FeatureDependencyError(
            "observability",
            'pip install "mini-harness[observability]"',
        ) from exc

    configure_observability(
        ObservabilityConfig(
            service_name=config.app.name,
            service_version=__version__,
            exporter=config.observability.exporter,
            otlp_endpoint=config.observability.otlp_endpoint,
            capture_content=False,
            log_level=config.observability.log_level,
        )
    )
    observability = Observability(config.app.name)
    return observability, HarnessMetrics(observability)


def _build_security(config, *, approval_store, budget_store, observability, metrics):
    if not config.security.enabled:
        return NoopSecurityService()

    security_config = SecurityConfig(
        max_input_chars=config.security.max_input_chars,
        max_output_chars=config.security.max_output_chars,
        max_tool_calls_per_run=config.security.max_tool_calls_per_run,
        detect_prompt_injection_signals=config.security.detect_prompt_injection_signals,
        block_prompt_injection_signals=config.security.block_prompt_injection_signals,
        approval_required_for_side_effects=config.security.approval_required_for_side_effects,
        disabled_tools=frozenset(config.security.disabled_tools),
        audit_path=config.security.audit_path,
    )
    input_guards = [InputLengthGuard(security_config.max_input_chars)]
    if security_config.detect_prompt_injection_signals:
        input_guards.append(
            PromptInjectionSignalGuard(
                block_on_signal=security_config.block_prompt_injection_signals
            )
        )
    return SecurityService(
        input_guards=input_guards,
        output_guards=[
            SecretOutputGuard(),
            OutputLengthGuard(security_config.max_output_chars),
        ],
        tool_policy=DefaultToolPolicy(
            config=security_config,
            approval_store=approval_store,
            budget_store=budget_store,
        ),
        audit_sink=JsonlAuditSink(security_config.audit_path),
        observability=observability,
        metrics=metrics,
    )


async def _register_rag(
    config: HarnessConfig,
    registry,
    database,
    observability,
    metrics,
):
    """RAG Extension：向量检索由 Chroma 承担，Embedding 固定使用 Qwen（DashScope）。

    chromadb 与 chroma_store 一起放进 try：chroma_store 在模块级 import chromadb，
    而 chromadb 属于 [rag] extra，隐藏的模块级依赖只有在这里捕获才能转成可执行提示。

    返回 `KnowledgeRepositoryCatalog`（多 RAG 仓库），供 HTTP 层使用；未启用时返回 None。
    """
    if not config.rag.enabled:
        return None
    try:
        import chromadb

        from harness.retrieval.catalog import KnowledgeRepositoryCatalog
        from harness.retrieval.chroma_store import ChromaVectorStore
        from harness.retrieval.chunkers import CharacterChunker
        from harness.retrieval.embeddings import QwenEmbeddingProvider
        from harness.retrieval.projector import RetrievalContextProjector
        from harness.retrieval.retriever import DenseRetriever, RetrievalPipeline
        from harness.retrieval.store import SQLiteKnowledgeRepositoryStore
    except ImportError as exc:
        raise FeatureDependencyError("rag", 'pip install "mini-harness[rag]"') from exc

    # model 为 None 时由 QwenEmbeddingProvider 读取 DASHSCOPE_MODEL。
    embedding_provider = QwenEmbeddingProvider(model=config.rag.embedding_model)
    projector = RetrievalContextProjector()

    # 一个进程只开一份 Chroma client，默认集合与各仓库集合共用它。
    client = chromadb.PersistentClient(path=config.rag.path)

    # 多仓库：仓库与文件元数据在 SQLite，向量按仓库分集合（一个仓库一个 collection）。
    catalog = KnowledgeRepositoryCatalog(
        store=SQLiteKnowledgeRepositoryStore(database),
        embedding_provider=embedding_provider,
        chunker=CharacterChunker(),
        vector_store_factory=lambda repository: ChromaVectorStore(
            path=config.rag.path,
            collection_name=repository.collection_name,
            client=client,
        ),
        storage_path=config.rag.storage_path,
        observability=observability,
        metrics=metrics,
    )

    # 旧的单集合路径完整保留：schema 与行为都不变，只是额外支持按 repository_id 检索。
    vector_store = ChromaVectorStore(
        path=config.rag.path,
        collection_name=config.rag.collection_name,
        client=client,
    )
    pipeline = RetrievalPipeline(
        retriever=DenseRetriever(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        ),
        observability=observability,
        metrics=metrics,
    )
    registry.register(
        build_rag_tool(
            name=config.rag.tool_name,
            retrieval_pipeline=pipeline,
            projector=projector,
            catalog=catalog,
        )
    )
    # Agent 写入 RAG 仓库的唯一入口：声明副作用 + 强制审批。
    registry.register(
        create_rag_write_tool(
            name=config.rag.write_tool_name,
            catalog=catalog,
        )
    )
    return catalog


async def _register_mcp(
    config: HarnessConfig,
    registry,
    database,
    observability,
    metrics,
):
    """MCP Extension：harness.toml 静态配置 + 前端登记（持久化）的 Server 一起生效。

    返回 (MCPManager, SQLiteMCPServerStore)；未启用时返回 (None, None)。
    静态与持久化的 Server 都在构建期注册，因此属于「能力在运行开始前确定」的一部分。
    """
    if not config.mcp.enabled:
        return None, None
    try:
        # 显式确认可选依赖存在：client.py 现在是延迟导入 SDK，若不在构建期检查，
        # 「启用 MCP 但没装 extra」会退化成第一次发现工具时才失败。
        import mcp  # noqa: F401

        from harness.mcp.config import (
            UNTRUSTED_TOOL_POLICY,
            MCPServerConfig,
            MCPTransport,
        )
        from harness.mcp.manager import MCPManager
        from harness.mcp.store import SQLiteMCPServerStore
    except ImportError as exc:
        raise FeatureDependencyError("mcp", 'pip install "mini-harness[mcp]"') from exc

    servers = []
    for item in config.mcp.servers:
        transport = MCPTransport(item.transport)
        servers.append(
            MCPServerConfig(
                name=item.name,
                transport=transport,
                url=item.url,
                command=item.command,
                args=item.args,
                enabled=item.enabled,
                required=item.required,
                tool_prefix=item.name if item.tool_prefix else None,
                allowed_tools=(
                    frozenset(item.allowed_tools) if item.allowed_tools else None
                ),
            )
        )

    # 前端登记过的 Server 在重启后要回来；同名冲突以 harness.toml 为准。
    store = SQLiteMCPServerStore(database)
    configured = {item.name for item in config.mcp.servers}
    for persisted in store.get_servers():
        if persisted.name in configured:
            continue
        servers.append(
            replace(
                persisted,
                default_tool_policy=UNTRUSTED_TOOL_POLICY,
            )
        )

    manager = MCPManager(
        servers,
        observability=observability,
        metrics=metrics,
    )
    await manager.register_all_tools(registry)
    return manager, store


def _build_model_provider(config: HarnessConfig, *, observability, metrics):
    """默认 Provider 是 DeepSeek；OpenAI 实现完整保留，可通过 provider 显式选择。

    - provider="deepseek"（默认）→ DeepSeekProvider，读 DEEPSEEK_API_KEY / DEEPSEEK_MODEL /
      DEEPSEEK_BASE_URL；model 不写时由 Provider 自己读 DEEPSEEK_MODEL。
    - provider="openai" → OpenAIProvider，读 OPENAI_API_KEY / OPENAI_MODEL。
    """
    provider = (config.app.provider or "deepseek").strip().lower()

    if provider == "deepseek":
        from harness.providers.deepseek_provider import DeepSeekProvider

        model_name = config.app.model or os.getenv("DEEPSEEK_MODEL")
        if not model_name:
            raise RuntimeError(
                "未配置模型。请设置 DEEPSEEK_MODEL，"
                "或在 harness.toml 的 [app].model 中指定。"
            )
        return DeepSeekProvider(
            model=model_name,
            observability=observability,
            metrics=metrics,
        )

    if provider == "openai":
        try:
            from harness.providers.openai_provider import OpenAIProvider
        except ImportError as exc:
            raise FeatureDependencyError("openai", "pip install mini-harness") from exc

        model_name = config.app.model or os.getenv("OPENAI_MODEL")
        if not model_name:
            raise RuntimeError(
                "未配置模型。请设置 OPENAI_MODEL，"
                "或在 harness.toml 的 [app].model 中指定。"
            )
        return OpenAIProvider(
            model=model_name,
            observability=observability,
            metrics=metrics,
        )

    raise RuntimeError(
        f"未知的 app.provider: {provider!r}；支持 'deepseek'（默认）与 'openai'。"
    )


async def assemble_runtime(
    config: HarnessConfig,
    *,
    tools: Iterable,
    middlewares: Iterable = (),
    model_provider=None,
) -> RuntimeBundle:
    """内部 Composition Root：复杂依赖全部收敛在这里，普通开发者无需手工组装。"""
    observability, metrics = _build_observability(config)

    # 进程内 Run 事件总线：Worker 侧的执行事实经由它流式推给 API / CLI 订阅者。
    events = RunEventBroker()

    database = Database(
        config.app.database_path,
        observability=observability,
    )
    database.initialize()

    durable_store = SQLiteDurableStore(database)
    approval_store = SQLiteApprovalStore(database)
    budget_store = SQLiteRunBudgetStore(database)
    idempotency_store = SQLiteIdempotencyStore(database)

    security = _build_security(
        config,
        approval_store=approval_store,
        budget_store=budget_store,
        observability=observability,
        metrics=metrics,
    )

    registry = ToolRegistry()
    from harness.app.desktop import DesktopService
    desktop = DesktopService(database, config)
    personal = PersonalCatalog(PersonalStore(database), desktop)
    for registered_tool in tools:
        registry.register(registered_tool)
    if config.server.mode == 'local':
        for personal_tool in personal.tools():
            registry.register(personal_tool)

    knowledge = await _register_rag(
        config, registry, database, observability, metrics
    )
    mcp, mcp_store = await _register_mcp(
        config, registry, database, observability, metrics
    )

    # 构建期结束：注册表封板，此后只接受 dynamic 注册（前端登记 MCP Server）。
    # 可复现性由 AgentRunner 在每个 Run 创建时写入 ToolContext.tool_names 的快照承担。
    registry.freeze()

    context_builder = ContextBuilder(
        budget=TokenBudget(
            max_context_tokens=config.context.max_context_tokens,
            reserved_output_tokens=config.context.reserved_output_tokens,
        ),
        token_counter=ApproxTokenCounter(),
        policy=ContextPolicy(
            recent_message_limit=config.context.recent_message_limit
        ),
    )

    if model_provider is None:
        model_provider = _build_model_provider(
            config,
            observability=observability,
            metrics=metrics,
        )

    executor = ToolExecutor(
        registry,
        observability=observability,
        metrics=metrics,
        security=security,
        middlewares=list(middlewares),
        idempotency_store=idempotency_store,
    )
    runner = AgentRunner(
        model=model_provider,
        registry=registry,
        executor=executor,
        context_builder=context_builder,
        observability=observability,
        system_instruction=config.app.system_instruction,
        max_steps=config.app.max_steps,
        emitter=events.publish,
    )

    application = PersistentAgentService(
        runner=runner,
        database=database,
        observability=observability,
        metrics=metrics,
        security=security,
    )
    durable = DurableAgentService(
        runner=runner,
        database=database,
        durable_store=durable_store,
        approval_store=approval_store,
        security=security,
        observability=observability,
        metrics=metrics,
        events=events.publish,
    )
    durable_config = DurableConfig(
        worker_count=config.durable.worker_count,
        lease_seconds=config.durable.lease_seconds,
        poll_interval_seconds=config.durable.poll_interval_seconds,
        idle_backoff_seconds=config.durable.idle_backoff_seconds,
        max_transitions_per_claim=config.durable.max_transitions_per_claim,
    )
    durable.desktop = desktop

    def worker_factory(index: int):
        return DurableWorker(
            runner=runner,
            durable_store=durable_store,
            lifecycle=durable,
            observability=observability,
            config=durable_config,
            worker_id=f"local_worker_{index}",
        )

    worker_pool = DurableWorkerPool(
        worker_factory=worker_factory,
        config=durable_config,
    )

    bundle = RuntimeBundle(
        application=application,
        durable=durable,
        worker_pool=worker_pool,
        observability=observability,
        metrics=metrics,
        security=security,
        database=database,
        durable_store=durable_store,
        registry=registry,
        model=model_provider,
        desktop=desktop,
        events=events,
        knowledge=knowledge,
        mcp=mcp,
        mcp_store=mcp_store,
        personal=personal,
    )

    # Same execution kernel, with no persistence/telemetry or callable tools.
    private_model = copy(model_provider)
    for attribute, value in (('observability', NoopObservability()), ('metrics', NoopMetrics()), ('store_responses', False)):
        if hasattr(private_model, attribute):
            setattr(private_model, attribute, value)
    if hasattr(private_model, '_histories'):
        private_model._histories = {}
    private_registry = ToolRegistry()
    private_registry.freeze()
    private_runner = AgentRunner(
        model=private_model, registry=private_registry, executor=ToolExecutor(private_registry),
        context_builder=context_builder, observability=NoopObservability(),
        system_instruction=config.app.system_instruction, max_steps=1,
        emitter=lambda run_id, event: bundle.temporary.emit(run_id, event),
    )
    bundle.temporary = TemporaryChats(private_runner, personal)

    async def scheduled_submit(**kwargs):
        return await submit_local(bundle, config, **kwargs)

    bundle.scheduler = AutomationScheduler(personal, scheduled_submit)

    if config.platform.enabled:
        bundle.platform = build_platform_runtime(config, bundle)
    return bundle


def build_platform_runtime(config: HarnessConfig, core: RuntimeBundle):
    """Phase 11 商业平台作为可选 Extension 保留，而不是 OSS 默认启动前置条件。"""
    try:
        from harness.platform import (
            ApiKeyManager,
            BillingService,
            CommercialPlatformService,
            PlatformConfig,
            QuotaService,
            SQLitePlatformStore,
            UsageReconciler,
            seed_default_plans,
        )
        from harness.platform.runtime import CommercialRuntime
    except ImportError as exc:
        raise FeatureDependencyError(
            "platform",
            'pip install "mini-harness[server]"',
        ) from exc

    store = SQLitePlatformStore(core.database)
    store.initialize()
    seed_default_plans(store)
    pepper = config.platform.api_key_pepper or os.getenv("HARNESS_API_KEY_PEPPER")
    if not pepper:
        raise RuntimeError(
            "Platform 模式需要 HARNESS_API_KEY_PEPPER；OSS local 模式不需要。"
        )
    platform_config = PlatformConfig(
        metering_poll_seconds=config.platform.metering_poll_seconds,
        usage_sync_batch_size=config.platform.usage_sync_batch_size,
    )
    api_keys = ApiKeyManager(
        store=store,
        pepper=pepper,
        prefix=platform_config.api_key_prefix,
    )
    quota = QuotaService(store)
    metering = UsageReconciler(
        platform_store=store,
        durable_store=core.durable_store,
        batch_size=platform_config.usage_sync_batch_size,
        poll_seconds=platform_config.metering_poll_seconds,
        metrics=core.metrics,
    )
    billing = BillingService(store=store, currency=platform_config.billing_currency)
    service = CommercialPlatformService(
        durable=core.durable,
        durable_store=core.durable_store,
        store=store,
        quota=quota,
        metering=metering,
        billing=billing,
        api_keys=api_keys,
        observability=core.observability,
        metrics=core.metrics,
    )
    return CommercialRuntime(
        core=core,
        store=store,
        api_keys=api_keys,
        service=service,
        metering=metering,
        billing=billing,
    )
