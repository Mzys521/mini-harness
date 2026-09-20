# 文件：tests/test_security_tool_result.py
import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
)

from harness.models import (
    ToolCall,
)
from harness.security import (
    SecurityConfig,
)
from harness.tools.definition import (
    ToolContext,
)
from harness.tools.executor import (
    ToolExecutor,
)
from harness.tools.factory import (
    tool_from_pydantic,
)
from harness.tools.registry import (
    ToolRegistry,
)
from tests.fakes_security import (
    build_fake_security,
)

class EmptyArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

@pytest.mark.asyncio
async def test_tool_result_is_redacted_before_model_projection() -> None:
    secret = (
        "sk-1234567890abcdefghijklmnop"
    )

    def read_secret():
        return {
            "token": secret
        }

    tool = tool_from_pydantic(
        name="read_demo_secret",
        description="返回测试数据。",
        args_model=EmptyArgs,
        handler=read_secret,
        side_effect=False,
    )

    (
        security,
        _,
        observability,
        metrics,
    ) = build_fake_security(
        config=SecurityConfig()
    )

    registry = ToolRegistry()
    registry.register(
        tool
    )
    executor = ToolExecutor(
        registry,
        observability=observability,
        metrics=metrics,
        security=security,
    )

    result = await executor.execute(
        ToolCall(
            call_id="call_secret",
            name="read_demo_secret",
            arguments={},
        ),
        ToolContext(
            run_id="run_secret_tool",
        ),
    )

    assert result.ok

    # 应用内部原始 data 仍存在，方便受控业务逻辑使用。
    assert result.data["token"] == secret

    # 但真正回流下一轮 LLM 的字符串必须已经过安全投影。
    model_output = (
        result.to_model_output()
    )
    assert secret not in model_output
    assert (
        "[REDACTED_API_KEY]"
        in model_output
    )