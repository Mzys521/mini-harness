from mcp.server import MCPServer

mcp = MCPServer("mini-harness-demo")

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """计算两个数字的乘法。"""
    return a * b

@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """演示只读订单查询。"""
    return {"order_id": order_id, "status": "paid"}

@mcp.resource("guide://harness")
def harness_guide() -> str:
    """演示 MCP Resource（MCP资源）。"""
    return "Harness 负责 Agent 的执行、工具、上下文和运行状态。"

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)