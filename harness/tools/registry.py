# 文件：harness/tools/registry.py
from harness.tools.definition import Tool
from harness.tools.errors import ToolNotFoundError


class ToolRegistry:
    """工具注册表: 集中管理所有可用工具，提供查找与 schema 导出

    注册表分两层，边界是显式的而不是约定：

    - **构建期注册**（`register(tool)`）：`freeze()` 之后继续注册会抛 `ValueError`。
      这是「一次运行用到哪些能力，必须在运行开始前确定」的执行点。
    - **运行期注册**（`register(tool, dynamic=True)`）：供前端登记 MCP Server 这类
      运行期扩展使用，配套 `unregister(name)`。可复现性不靠禁止注册来保证，而是
      由 `AgentRunner` 在创建 Run 时把当前工具名写入 `ToolContext.tool_names` 的
      快照承担——已经在跑的 Run 看不到新工具，新提交的 Run 才看得到。
    """

    def __init__(self) -> None:
        """初始化一个空的工具注册表"""
        self._tools : dict[str , Tool] = {}
        self._dynamic : set[str] = set()
        self._frozen = False

    def register(self , tool : Tool , * , dynamic : bool = False)->None:
        """注册一个工具。
        参数 tool: 工具定义；名称重复时抛 ValueError
        参数 dynamic: 运行期扩展（例如前端登记的 MCP Server）；freeze 后只有它能注册
        """
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        if self._frozen and not dynamic:
            raise ValueError(
                "工具注册表已冻结：请在 build 前注册，"
                "或用 register(tool, dynamic=True) 做运行期扩展。"
            )
        self._tools[tool.name] = tool
        if dynamic:
            self._dynamic.add(tool.name)

    def unregister(self , name : str)->None:
        """摘除一个运行期注册的工具；构建期注册的工具不允许摘除（幂等）。"""
        if name not in self._tools:
            return
        if name not in self._dynamic:
            raise ValueError(f"构建期注册的工具不能摘除: {name}")
        del self._tools[name]
        self._dynamic.discard(name)

    def freeze(self)->None:
        """封板：此后只接受 dynamic 注册。由组合根在构建结束时调用。"""
        self._frozen = True

    def is_dynamic(self , name : str)->bool:
        """该工具是否为运行期注册（可被 unregister 摘除）。"""
        return name in self._dynamic

    def get(self , name: str) -> Tool:
        """按名称查找工具。
        参数 name: 工具名
        返回: 对应的 Tool；不存在时抛 ToolNotFoundError
        """
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError(f"Tool {name} 不存在") from None
    
    def list_tools(self) -> list[Tool]:
        """返回全部已注册的工具列表"""
        return list(self._tools.values())

    def openai_schemas(self , names : frozenset[str] | None = None) -> list[dict]:
        """返回工具的 OpenAI schema 列表(用于发送给模型)

        参数 names: 工具名快照；为 None 时导出全部（旧调用方语义不变）
        """
        return [
            tool.to_openai_schema()
            for tool in self._tools.values()
            if names is None or tool.name in names
        ]
