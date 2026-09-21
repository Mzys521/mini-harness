# 文件：harness/app/application.py
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable

from harness.app.assembly import assemble_runtime
from harness.app.config import HarnessConfig, load_config
from harness.app.plugins import load_entrypoint_plugins
from harness.app.tooling import get_declared_tool, to_tool
from harness.tools.definition import Tool


class HarnessApp:
    """mini-harness 的开发者入口。

    普通开发者只需要：配置、Tool、Plugin；复杂依赖由内部 Composition Root 完成。
    """

    def __init__(
        self,
        config: HarnessConfig | None = None,
        *,
        model_provider=None,
    ) -> None:
        self.config = config or HarnessConfig()
        self._model_provider = model_provider
        self._tools: list[Tool] = []
        self._middlewares: list[object] = []
        self._plugins: list[object] = []
        self._runtime = None

        if self.config.plugins.auto_discover:
            self.discover_plugins(self.config.plugins.names)

    @classmethod
    def from_toml(
        cls,
        path: str | Path = "harness.toml",
        *,
        optional: bool = True,
        model_provider=None,
    ) -> "HarnessApp":
        return cls(
            load_config(path, optional=optional),
            model_provider=model_provider,
        )

    def add_tool(self, value) -> Tool:
        """接受旧 Tool、@harness.tool 函数或普通 typed callable。"""
        self._ensure_mutable()
        registered = value if isinstance(value, Tool) else get_declared_tool(value)
        if registered is None and callable(value):
            registered = to_tool(value)
        if not isinstance(registered, Tool):
            raise TypeError("add_tool() 需要 Tool 或带类型注解的 callable。")
        if any(item.name == registered.name for item in self._tools):
            raise ValueError(f"tool already added: {registered.name}")
        self._tools.append(registered)
        return registered

    def add_tools(self, *values) -> "HarnessApp":
        """批量注册；列表 / 元组等可迭代 Tool 集合会被展开，便于沿用旧 tool_list。"""
        for value in values:
            if isinstance(value, (list, tuple, set, frozenset)):
                for item in value:
                    self.add_tool(item)
                continue
            self.add_tool(value)
        return self

    def tool(self, func=None, **options):
        """注册 Tool 并返回原函数，因此函数仍可直接单元测试。"""
        def decorate(target):
            self.add_tool(to_tool(target, **options))
            return target

        if func is not None:
            return decorate(func)
        return decorate

    def add_middleware(self, middleware) -> "HarnessApp":
        self._ensure_mutable()
        self._middlewares.append(middleware)
        return self

    def use(self, plugin) -> "HarnessApp":
        self._ensure_mutable()
        register = getattr(plugin, "register", None)
        if register is None:
            raise TypeError("Plugin 必须实现 register(app) 方法。")
        register(self)
        self._plugins.append(plugin)
        return self

    def discover_plugins(self, names: tuple[str, ...] = ()) -> "HarnessApp":
        for plugin in load_entrypoint_plugins(names=names):
            self.use(plugin)
        return self

    @property
    def runtime(self):
        if self._runtime is None:
            raise RuntimeError("Runtime 尚未 build；请先 await app.build()。")
        return self._runtime

    async def build(self, *, force: bool = False):
        if self._runtime is not None and not force:
            return self._runtime
        self._runtime = await assemble_runtime(
            self.config,
            tools=self._tools,
            middlewares=self._middlewares,
            model_provider=self._model_provider,
        )
        return self._runtime

    def local_permissions(self) -> frozenset[str]:
        """Local-first 模式默认授予“已注册能力”所需权限，不要求开发者再维护第二份权限清单。"""
        tools = list(self._tools)
        if self._runtime is not None:
            tools = self._runtime.registry.list_tools()
        permissions: set[str] = set()
        for item in tools:
            permissions.update(item.required_permissions)
        return frozenset(permissions)

    async def ask(
        self,
        user_input: str,
        *,
        conversation_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ):
        runtime = await self.build()
        return await runtime.application.ask(
            user_id=user_id or self.config.app.local_user_id,
            tenant_id=tenant_id or self.config.app.local_tenant_id,
            user_input=user_input,
            permissions=self.local_permissions(),
            conversation_id=conversation_id,
        )

    async def submit(
        self,
        user_input: str,
        *,
        conversation_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ):
        runtime = await self.build()
        return await runtime.durable.submit(
            user_id=user_id or self.config.app.local_user_id,
            tenant_id=tenant_id or self.config.app.local_tenant_id,
            user_input=user_input,
            permissions=self.local_permissions(),
            conversation_id=conversation_id,
        )

    async def get_run(self, run_id: str):
        runtime = await self.build()
        return runtime.durable.get_result(run_id)

    async def approve(self, run_id: str, *, approved_by: str = "local_user") -> None:
        runtime = await self.build()
        runtime.durable.approve(run_id=run_id, approved_by=approved_by)

    async def cancel(self, run_id: str) -> None:
        runtime = await self.build()
        runtime.durable.cancel(run_id=run_id)

    async def chat(self, *, durable: bool = True) -> None:
        runtime = await self.build()
        if durable:
            stop_event = asyncio.Event()
            worker_task = asyncio.create_task(
                runtime.worker_pool.run_forever(stop_event=stop_event)
            )
            try:
                await self._durable_chat_loop()
            finally:
                stop_event.set()
                await worker_task
            return
        await self._immediate_chat_loop()

    async def _immediate_chat_loop(self) -> None:
        conversation_id = None
        while True:
            question = input("\n你（exit 退出）：").strip()
            if question.lower() == "exit":
                return
            result = await self.ask(question, conversation_id=conversation_id)
            conversation_id = result.conversation_id
            print("\nAgent：", result.output)

    async def _durable_chat_loop(self) -> None:
        from harness.durable.models import DurableRunStatus

        conversation_id = None
        while True:
            question = input("\n你（exit 退出）：").strip()
            if question.lower() == "exit":
                return
            submission = await self.submit(question, conversation_id=conversation_id)
            conversation_id = submission.conversation_id
            if submission.blocked:
                print("\nAgent：", submission.output)
                continue

            while True:
                await asyncio.sleep(0.1)
                result = await self.get_run(submission.run_id)
                if result.status == DurableRunStatus.COMPLETED:
                    print("\nAgent：", result.output)
                    break
                if result.status == DurableRunStatus.WAITING:
                    print(f"\nHarness：等待审批工具 {result.waiting_tool_name}")
                    answer = input("是否批准？[y/N]：").strip().lower()
                    if answer == "y":
                        await self.approve(submission.run_id)
                        continue
                    await self.cancel(submission.run_id)
                    print("已请求取消。")
                    break
                if result.status in {DurableRunStatus.FAILED, DurableRunStatus.CANCELLED}:
                    print("\nHarness：", result.status.value, result.error_message or "")
                    break

    async def create_http_app(self):
        from harness.app.server import create_http_app

        runtime = await self.build()
        return create_http_app(self, runtime)

    def cli(self, argv=None) -> None:
        from harness.cli import run_cli

        run_cli(self, argv=argv)

    def _ensure_mutable(self) -> None:
        if self._runtime is not None:
            raise RuntimeError(
                "Runtime 已经 build，不能再修改 Tool/Plugin；请在 build 前完成注册。"
            )
