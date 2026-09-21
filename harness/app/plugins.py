# 文件：harness/app/plugins.py
from __future__ import annotations

from importlib.metadata import entry_points
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from harness.app.application import HarnessApp

PLUGIN_GROUP = "mini_harness.plugins"


class HarnessPlugin(Protocol):
    """第三方插件只需要实现一个 register(app) 方法。"""
    name: str

    def register(self, app: "HarnessApp") -> None:
        ...


def load_entrypoint_plugins(*, names: tuple[str, ...] = ()) -> list[object]:
    """按 PyPA Entry Points 发现插件；默认由调用方明确开启，不隐式执行第三方代码。"""
    selected = entry_points(group=PLUGIN_GROUP)
    allowed = set(names)
    plugins: list[object] = []
    for entry in selected:
        if allowed and entry.name not in allowed:
            continue
        loaded = entry.load()
        plugin = loaded() if isinstance(loaded, type) else loaded
        plugins.append(plugin)
    return plugins
