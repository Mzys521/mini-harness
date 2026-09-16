from dataclasses import dataclass

@dataclass(frozen=True)
class MCPResourceText:
    server_name: str
    uri: str
    text: str

async def read_text_resource(*, gateway, uri: str) -> MCPResourceText:
    result = await gateway.read_resource(uri)
    parts: list[str] = []

    for item in result.contents:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)

    return MCPResourceText(
        server_name=gateway.config.name,
        uri=uri,
        text="\n".join(parts),
    )