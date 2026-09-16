
import json

from harness.mcp.errors import MCPToolCallError
from harness.tools.definition import Tool

def result_to_text(result) -> str:
    """把不同 MCP Content Block（内容块）规范化成当前 Harness 可处理输出。"""
    if result.structured_content is not None:
        return json.dumps(
            result.structured_content, 
            ensure_ascii=False, 
            default=str
        )

    parts : list[str] = []
    for block in result.content:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else str(block))

    return "\n".join(parts)


def adapt_mcp_tool(*, spec, gateway, policy) -> Tool:
    """远程 MCP Tool（MCP工具）→ 内部统一 Tool（工具）。"""

    async def handler(**arguments):
        result = await gateway.call_tool(spec.remote_name, arguments)

        # Tool Error Result（工具错误结果）和 Transport Failure（传输失败）语义不同。
        if result.is_error:
            raise MCPToolCallError(
                f"远程 Tool 执行失败：{spec.server_name}/{spec.remote_name}"
            )

        return result_to_text(result)

    return Tool(
        name=spec.local_name,
        description=spec.description,
        input_schema=spec.input_schema,
        handler=handler,
        timeout_seconds=policy.timeout_seconds,
        max_retries=policy.max_retries,
        required_permissions=frozenset({
            f"mcp.{spec.server_name}.{spec.remote_name}"
        }),
        side_effects=policy.side_effect,
        source="mcp",
        metadata={
            "mcp_server": spec.server_name,
            "mcp_remote_name": spec.remote_name,
            "mcp_annotations": spec.annotations,
            "idempotent": policy.idempotent,
            "requires_approval": policy.requires_approval,
        },
    )





























