# 文件：harness/cli.py
from __future__ import annotations

import argparse
import asyncio
import importlib
import os
import sys
from dataclasses import replace
from pathlib import Path

from harness.app.application import HarnessApp
from harness.app.config import load_config
from harness.app.errors import FeatureDependencyError


def _load_object(ref: str):
    module_name, sep, attr = ref.partition(":")
    if not sep:
        raise ValueError("App factory 必须使用 'module:object' 格式，例如 main:app")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _ensure_project_on_path(config_path: str) -> None:
    """让 console_scripts 入口也能 import 项目自己的模块（如 app_tools）。

    `python main.py serve` 会把仓库根目录放进 sys.path[0]，但装好之后运行的
    `mini-harness serve` 不会——那时 `import app_tools` 会失败，工具被静默丢弃。
    这里把当前工作目录与配置文件所在目录补进 sys.path。
    """
    candidates = [Path.cwd(), Path(config_path).expanduser().resolve().parent]
    for candidate in candidates:
        text = str(candidate)
        if text not in sys.path:
            sys.path.insert(0, text)


def load_project_app(config_path: str = "harness.toml") -> HarnessApp:
    config = load_config(config_path, optional=True)
    ref = os.getenv("HARNESS_APP", config.app.factory)
    _ensure_project_on_path(config_path)
    try:
        value = _load_object(ref)
    except ModuleNotFoundError as exc:
        # 只有「连工厂模块本身都找不到」才是合法的零配置回退；
        # 模块存在、但它内部 import 失败必须原样抛出，否则工具会被悄悄丢光。
        missing = exc.name or ""
        if missing.split(".")[0] not in {ref.partition(":")[0].split(".")[0], ""}:
            raise
        return HarnessApp(config)
    except AttributeError:
        return HarnessApp(config)
    if isinstance(value, HarnessApp):
        return value
    if callable(value):
        created = value()
        if isinstance(created, HarnessApp):
            return created
    raise TypeError(f"{ref} 必须是 HarnessApp 或返回 HarnessApp 的 factory。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mini-harness",
        description="mini-harness developer CLI",
    )
    parser.add_argument("--config", default="harness.toml")
    sub = parser.add_subparsers(dest="command")

    chat = sub.add_parser("chat", help="启动本地 Chat；默认 Durable Mode")
    chat.add_argument("--immediate", action="store_true")

    serve = sub.add_parser("serve", help="启动 HTTP API")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    sub.add_parser("doctor", help="检查配置和可选依赖，不调用模型")
    sub.add_parser("plugins", help="显示当前已安装的 mini-harness 插件")
    sub.add_parser("security-check", help="验证 Phase 9 Security")
    sub.add_parser("durable-check", help="验证 Phase 10 Durable Execution")

    eval_parser = sub.add_parser("eval", help="运行 Phase 8 Evaluation Dataset")
    eval_parser.add_argument("--dataset", default="evals/datasets/smoke.jsonl")
    eval_parser.add_argument("--suite", default="smoke")
    eval_parser.add_argument("--report", default="evals/reports/latest.json")
    eval_parser.add_argument("--judge-model", default=None)
    eval_parser.add_argument(
        "--judge-provider",
        default="deepseek",
        choices=("deepseek", "openai"),
        help="Judge Provider；默认 deepseek，无需 OPENAI_API_KEY",
    )

    platform = sub.add_parser("platform-init", help="初始化可选 Phase 11 Platform Extension")
    platform.add_argument("--database", default=None)

    return parser


def run_cli(app: HarnessApp, *, argv=None) -> None:
    args = build_parser().parse_args(argv)
    command = args.command or "chat"
    try:
        if command == "chat":
            asyncio.run(app.chat(durable=not getattr(args, "immediate", False)))
            return
        if command == "serve":
            asyncio.run(_serve(app, args))
            return
        if command == "doctor":
            _doctor(app)
            return
        if command == "plugins":
            _plugins()
            return
        if command == "security-check":
            from harness.app.checks import run_security_check
            asyncio.run(run_security_check())
            return
        if command == "durable-check":
            from harness.app.checks import run_durable_check
            asyncio.run(run_durable_check())
            return
        if command == "eval":
            asyncio.run(_eval(app, args))
            return
        if command == "platform-init":
            _platform_init(app, args)
            return
    except FeatureDependencyError as exc:
        raise SystemExit(str(exc)) from exc


def main() -> None:
    # console_scripts 入口：默认加载当前项目 main:app。
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default="harness.toml")
    known, _ = pre.parse_known_args()
    app = load_project_app(known.config)
    run_cli(app)


async def _serve(app: HarnessApp, args) -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise FeatureDependencyError(
            "server",
            'pip install "mini-harness[server]"',
        ) from exc

    if args.host is not None or args.port is not None:
        app.config = replace(
            app.config,
            server=replace(
                app.config.server,
                host=args.host or app.config.server.host,
                port=args.port or app.config.server.port,
            ),
        )

    api = await app.create_http_app()
    config = uvicorn.Config(
        api,
        host=app.config.server.host,
        port=app.config.server.port,
        log_level="info",
    )
    await uvicorn.Server(config).serve()


def _doctor(app: HarnessApp) -> None:
    config = app.config
    provider = (config.app.provider or "deepseek").strip().lower()
    checks: list[tuple[str, bool, str]] = []

    if provider == "openai":
        checks.append(
            (
                "OPENAI_MODEL",
                bool(config.app.model or os.getenv("OPENAI_MODEL")),
                "required at runtime",
            )
        )
        checks.append(
            ("OPENAI_API_KEY", bool(os.getenv("OPENAI_API_KEY")), "required by OpenAI provider")
        )
    else:
        checks.append(
            (
                "DEEPSEEK_MODEL",
                bool(config.app.model or os.getenv("DEEPSEEK_MODEL")),
                "required at runtime",
            )
        )
        checks.append(
            (
                "DEEPSEEK_API_KEY",
                bool(os.getenv("DEEPSEEK_API_KEY")),
                "required by default DeepSeek provider",
            )
        )

    if config.rag.enabled:
        # Embedding 固定使用 Qwen（DashScope OpenAI 兼容模式）。
        checks.append(
            (
                "DASHSCOPE_API_KEY",
                bool(os.getenv("DASHSCOPE_API_KEY")),
                "required by Qwen embedding provider (rag)",
            )
        )

    features = {
        "rag": (config.rag.enabled, "chromadb", 'mini-harness[rag]'),
        "mcp": (config.mcp.enabled, "mcp", 'mini-harness[mcp]'),
        "server": (config.server.enabled, "fastapi", 'mini-harness[server]'),
        "observability": (
            config.observability.enabled,
            "opentelemetry.sdk",
            'mini-harness[observability]',
        ),
        "platform": (config.platform.enabled, "fastapi", 'mini-harness[server]'),
    }
    for name, (enabled, module, extra) in features.items():
        if not enabled:
            checks.append((name, True, "disabled"))
            continue
        try:
            importlib.import_module(module)
            checks.append((name, True, "installed"))
        except ImportError:
            checks.append((name, False, f'pip install "{extra}"'))

    print("mini-harness doctor")
    print(f"provider={provider} database={config.app.database_path}")
    failed = False
    for name, ok, detail in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
        failed = failed or not ok
    if failed:
        raise SystemExit(2)


def _plugins() -> None:
    from importlib.metadata import entry_points

    from harness.app.plugins import PLUGIN_GROUP

    items = entry_points(group=PLUGIN_GROUP)
    if not items:
        print("No installed mini-harness plugins.")
        return
    for item in items:
        print(f"{item.name} -> {item.value}")


async def _eval(app: HarnessApp, args) -> None:
    from harness.evaluation import (
        AnswerContainsEvaluator,
        EvaluationRunner,
        ForbiddenToolEvaluator,
        HarnessEvaluationTarget,
        MaxStepsEvaluator,
        RequiredToolEvaluator,
        SecurityPolicyEvaluator,
        load_jsonl_dataset,
        write_json_report,
    )

    runtime = await app.build()
    target = HarnessEvaluationTarget(
        application=runtime.application,
        user_id="eval_user",
        tenant_id="eval_tenant",
        permissions=app.local_permissions(),
    )
    evaluators = [
        AnswerContainsEvaluator(),
        RequiredToolEvaluator(),
        ForbiddenToolEvaluator(),
        MaxStepsEvaluator(),
        SecurityPolicyEvaluator(),
    ]
    if args.judge_model:
        evaluators.append(_build_judge(args.judge_provider, args.judge_model))
    runner = EvaluationRunner(
        target=target,
        evaluators=evaluators,
        observability=runtime.observability,
        metrics=runtime.metrics,
    )
    result = await runner.run(
        suite_name=args.suite,
        cases=load_jsonl_dataset(args.dataset),
    )
    path = write_json_report(result, args.report)
    print(f"pass_rate={result.summary.pass_rate:.2%}")
    print(f"average_score={result.summary.average_score:.3f}")
    print(f"report={path}")


def _build_judge(provider: str, model: str):
    """LLM Judge：默认 DeepSeek；OpenAI 实现完整保留，可显式切换。"""
    if provider == "openai":
        from harness.evaluation.judge import OpenAIJudgeEvaluator

        return OpenAIJudgeEvaluator(model=model, pass_threshold=0.8)

    from harness.evaluation.judge import DeepSeekJudgeEvaluator

    return DeepSeekJudgeEvaluator(model=model, pass_threshold=0.8)


def _platform_init(app: HarnessApp, args) -> None:
    from harness.persistence.database import Database
    from harness.platform import ApiKeyManager, SQLitePlatformStore, seed_default_plans

    pepper = app.config.platform.api_key_pepper or os.getenv("HARNESS_API_KEY_PEPPER")
    if not pepper:
        raise SystemExit(
            "Platform Extension 才需要 HARNESS_API_KEY_PEPPER；请设置后重试。"
        )
    database_path = args.database or app.config.app.database_path
    database = Database(database_path)
    database.initialize()
    store = SQLitePlatformStore(database)
    store.initialize()
    seed_default_plans(store)
    api_keys = ApiKeyManager(store=store, pepper=pepper, prefix="mhk")

    if store.get_tenant("_platform") is None:
        store.create_tenant(tenant_id="_platform", name="Platform Operator", plan_id="operator_v1")
    if store.get_tenant("tenant_demo") is None:
        store.create_tenant(tenant_id="tenant_demo", name="Demo Tenant", plan_id="pro_v1")

    admin_key = api_keys.create_key(
        tenant_id="_platform",
        name="platform-admin",
        scopes=frozenset({"platform:admin"}),
    )
    demo_key = api_keys.create_key(
        tenant_id="tenant_demo",
        name="demo-client",
        scopes=frozenset({
            "runs:create", "runs:read", "runs:approve", "runs:cancel", "usage:read", "billing:read"
        }),
    )
    print("Platform Extension 初始化完成；明文 Key 只显示本次：")
    print("ADMIN_API_KEY=", admin_key.secret)
    print("DEMO_API_KEY=", demo_key.secret)


if __name__ == "__main__":
    main()
