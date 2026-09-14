from harness.tools.definition import Tool
from harness.tools.errors import ToolNotFoundError

class ToolRegistry:
    """工具注册表: 集中管理所有可用工具，提供查找与 schema 导出"""
    
    def __init__(self) -> None:
        """初始化一个空的工具注册表"""
        self._tools : dict[str , Tool] = {}
    
    def register(self , tool : Tool)->None:
        """注册一个工具。
        参数 tool: 工具定义；名称重复时抛 ValueError
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} 已经注册")
        self._tools[tool.name] = tool

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

    def openai_schema(self) -> list[dict]:
        """返回全部工具的 OpenAI schema 列表(用于发送给模型)"""
        return [tool.to_openai_schema() for tool in self._tools.values()]




