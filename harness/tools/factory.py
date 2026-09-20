# 文件：harness/tools/factory.py
from pydantic import BaseModel

from harness.tools.definition import Tool

def tool_from_pydantic(
    *,
    name: str,
    description: str,
    args_model: type[BaseModel],
    handler,
    timeout_seconds: float = 10.0,
    max_retries: int = 0,
    required_permissions: frozenset[str] = frozenset(),
    side_effect: bool = False,
    idempotent: bool = False,
    requires_approval: bool = False,
    source: str = "local",
    metadata: dict | None = None,
    inject_context: bool = False,
) -> Tool:
    return Tool(
        name=name,
        description=description,
        input_schema=args_model.model_json_schema(),
        handler=handler,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        required_permissions=required_permissions,
        side_effect=side_effect,
        idempotent=idempotent,
        requires_approval=requires_approval,
        source=source,
        metadata=metadata or {},
        inject_context=inject_context,
    )
