"""供真实 MCP stdio 集成测试启动的最小服务器。"""

from mcp.server import MCPServer

server = MCPServer("mini-harness-integration-test")


@server.tool()
def echo(value: str) -> str:
    """原样返回输入。"""
    return value


if __name__ == "__main__":
    server.run()
