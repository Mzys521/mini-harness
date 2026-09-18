"""
    工具工厂模块
"""
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
    source: str = "local", 
    metadata: dict | None = None,
    inject_context: bool = False
    ) -> Tool:
    """本地 Pydantic Model（Pydantic数据模型）在进入 Runtime 前统一成 JSON Schema。"""
    return Tool(
        name=name, 
        description=description, 
        input_schema=args_model.model_json_schema(), 
        handler=handler, 
        timeout_seconds=timeout_seconds, 
        max_retries=max_retries, 
        required_permissions=required_permissions, 
        side_effect=side_effect, 
        source=source, 
        metadata=metadata or {},
        inject_context=inject_context,
    )







