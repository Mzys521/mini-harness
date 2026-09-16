import pytest
from pydantic import BaseModel,ConfigDict

from harness.models import ToolCall
from harness.tools.definition import ToolContext
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry
from harness.tools.factory import tool_from_pydantic
from harness.tools.result import ToolStatus


class AddArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: float
    b: float

def add(a : float , b : float) -> float:
    """测试用加法函数。参数 a/b: 两个加数"""
    return a + b

# 测试工具成功执行
@pytest.mark.asyncio
async def test_tool_success():
    """正常调用应返回 SUCCESS，且 data 为计算结果。"""
    registry = ToolRegistry()
    registry.register(tool_from_pydantic(
        name="add",
        description="add",
        args_model=AddArgs,
        handler=add,
    ))

    executor = ToolExecutor(registry=registry)
    result = await executor.execute(
        ToolCall("call-1", "add", {"a":1, "b":2}),
        ToolContext(run_id="run-1"),
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.data == 3

# 测试工具参数错误
@pytest.mark.asyncio
async def test_invalid_arguments():
    """传入多余字段(extra=forbid)应返回 INVALID_ARGUMENTS。"""
    registry = ToolRegistry()
    registry.register(tool_from_pydantic(
        name="add",
        description="add",
        args_model=AddArgs,
        handler=add,
    ))

    result = await ToolExecutor(registry).execute(
        ToolCall(
            "call-2",
            "add",
            {"a": 1, "b": 2, "hello": "world"},
        ),
        ToolContext(run_id="run-1"),
    )

    assert result.status == ToolStatus.INVALID_ARGUMENTS

# 测试工具超时
import asyncio

class SleepArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seconds: float

async def slow(seconds: float):
    """测试用慢函数。参数 seconds: 阻塞秒数"""
    await asyncio.sleep(seconds)
    return "done"

@pytest.mark.asyncio
async def test_timeout():
    """handler 耗时超过 timeout_seconds 应返回 TIMEOUT。"""
    registry = ToolRegistry()
    registry.register(tool_from_pydantic(
        name="slow",
        description="slow",
        args_model=SleepArgs,
        handler=slow,
        timeout_seconds=0.05,
    ))

    result = await ToolExecutor(registry).execute(
        ToolCall("call-3", "slow", {"seconds": 1}),
        ToolContext(run_id="run-1"),
    )

    assert result.status == ToolStatus.TIMEOUT

# 测试工具权限 denied
@pytest.mark.asyncio
async def test_permission_denied():
    """上下文权限不足时应返回 PERMISSION_DENIED。"""
    registry = ToolRegistry()
    registry.register(tool_from_pydantic(
        name="dangerous",
        description="dangerous",
        args_model=AddArgs,
        handler=add,
        required_permissions=frozenset({"dangerous.execute"}),
    ))

    result = await ToolExecutor(registry).execute(
        ToolCall("call-4", "dangerous", {"a": 1, "b": 2}),
        ToolContext(run_id="run-1"),
    )

    assert result.status == ToolStatus.PERMISSION_DENIED


# 测试工具重试
from harness.tools.errors import RetryableToolError

class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

@pytest.mark.asyncio
async def test_retry():
    """抛出 RetryableToolError 的工具重试后成功，attempts 应为 3。"""
    attempts = 0

    async def flaky():
        """前两次抛可重试错误，第三次成功"""
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RetryableToolError("temporary failure")
        return "ok"

    registry = ToolRegistry()
    registry.register(tool_from_pydantic(
        name="flaky",
        description="flaky",
        args_model=EmptyArgs,
        handler=flaky,
        max_retries=2,
    ))

    result = await ToolExecutor(registry).execute(
        ToolCall("call-5", "flaky", {}),
        ToolContext(run_id="run-1"),
    )

    assert result.status == ToolStatus.SUCCESS
    assert result.attempts == 3



