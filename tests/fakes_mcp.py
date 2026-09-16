from dataclasses import dataclass, field

from harness.mcp.models import MCPToolSpec


@dataclass
class FakeToolResult:
    """模仿 MCP SDK 的 CallToolResult，只保留 adapter 会读取的字段。"""
    is_error: bool = False
    structured_content: dict | None = None
    content: list = field(default_factory=list)


class FakeMCPGateway:
    """测试用 MCP Gateway：不联网，记录每一次远程调用。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []    # 远程调用记录，用于断言"没有触达远程"

    async def list_tools(self) -> list[MCPToolSpec]:
        return [
            MCPToolSpec(
                server_name="fake",
                remote_name="multiply",
                local_name="fake__multiply",
                description="Fake remote multiply（测试用远程乘法工具）。",
                input_schema={
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                    "additionalProperties": False,
                },
            )
        ]

    async def call_tool(self, tool_name: str, arguments: dict) -> FakeToolResult:
        self.calls.append((tool_name, arguments))
        return FakeToolResult(structured_content={"result": arguments})