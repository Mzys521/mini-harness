import asyncio
from mcp import Client


"""
$env:NO_PROXY = "localhost,127.0.0.1"
python -m scripts.inspect_mcp_server
"""

async def main() -> None:
    async with Client("http://localhost:8000/mcp") as client:
        print("协议版本：", client.protocol_version)
        cursor = None

        while True:
            result = await client.list_tools(cursor=cursor)
            for tool in result.tools:
                print(tool.name, tool.input_schema)
            cursor = result.next_cursor
            if cursor is None:
                break

        result = await client.call_tool("multiply", {"a": 6, "b": 7})
        print("is_error：", result.is_error)
        print("structured_content：", result.structured_content)

if __name__ == "__main__":
    asyncio.run(main())