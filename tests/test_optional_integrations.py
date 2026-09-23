"""真实可选依赖的边界测试；Core 环境跳过，CI all extras 作强制验证。"""

import importlib.util
import sys
from pathlib import Path

import pytest

from harness.mcp.config import MCPServerConfig, MCPTransport
from harness.mcp.discovery import discover_and_register
from harness.retrieval.models import Chunk
from harness.tools.registry import ToolRegistry


@pytest.mark.skipif(importlib.util.find_spec("mcp") is None, reason="需要 [mcp] extra")
@pytest.mark.asyncio
async def test_mcp_gateway_connects_to_real_stdio_server():
    from harness.mcp.adapter import result_to_text
    from harness.mcp.client import MCPGateway

    server_path = Path(__file__).parent / "fixtures" / "mcp_stdio_server.py"
    gateway = MCPGateway(
        MCPServerConfig(
            name="integration",
            transport=MCPTransport.STDIO,
            command=sys.executable,
            args=(str(server_path),),
        )
    )

    specs = await gateway.list_tools()
    assert [spec.remote_name for spec in specs] == ["echo"]
    assert specs[0].input_schema["type"] == "object"

    registry = ToolRegistry()
    assert await discover_and_register(gateway=gateway, registry=registry) == 1
    assert registry.get("integration__echo").metadata["mcp_server"] == "integration"

    result = await gateway.call_tool("echo", {"value": "hello from stdio"})
    assert result.is_error is False
    assert "hello from stdio" in result_to_text(result)


@pytest.mark.skipif(
    importlib.util.find_spec("chromadb") is None, reason="需要 [rag] extra"
)
def test_chroma_collections_persist_filter_and_delete(tmp_path):
    from harness.retrieval.chroma_store import ChromaVectorStore

    path = str(tmp_path / "vectors")
    first = ChromaVectorStore(path=path, collection_name="repo_first")
    second = ChromaVectorStore(path=path, collection_name="repo_second", client=first.client)
    chunks = [
        Chunk(
            id="a",
            document_id="doc_a",
            text="first document",
            index=0,
            metadata={"repository_id": "first"},
        ),
        Chunk(
            id="b",
            document_id="doc_b",
            text="second document",
            index=0,
            metadata={"repository_id": "second"},
        ),
    ]
    first.upsert(chunks=chunks, embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    second.upsert(chunks=[chunks[0]], embeddings=[[1.0, 0.0, 0.0]])

    reopened = ChromaVectorStore(path=path, collection_name="repo_first", client=first.client)
    assert [item.chunk.id for item in reopened.search(query_embedding=[1.0, 0.0, 0.0])] == [
        "a",
        "b",
    ]
    assert [
        item.chunk.id
        for item in reopened.search(
            query_embedding=[1.0, 0.0, 0.0], where={"repository_id": "second"}
        )
    ] == ["b"]

    reopened.delete_by_document("doc_a")
    assert [item.chunk.id for item in first.search(query_embedding=[1.0, 0.0, 0.0])] == ["b"]

    reopened.delete_all()
    assert reopened.search(query_embedding=[1.0, 0.0, 0.0]) == []
    assert [item.chunk.id for item in second.search(query_embedding=[1.0, 0.0, 0.0])] == [
        "a"
    ]
