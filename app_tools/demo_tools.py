import asyncio
from pydantic import BaseModel , ConfigDict
from harness.tools.definition import Tool


class SleepArgs(BaseModel):
    """sleep 工具入参(禁止额外字段)
    注意: 字段名 secondes 与 handler 参数名 seconds 不一致，会导致调用失败
    """
    model_config = ConfigDict(extra="forbid")
    secondes: float    # 等待的秒数

async def sleep_handle(seconds: float) -> str:
    """异步等待指定秒数。
    参数 seconds: 等待的秒数
    返回: 完成提示文本
    """
    await asyncio.sleep(seconds)
    return f"Slept for {seconds} seconds"

sleep_tool = Tool(
    name="sleep",
    description="等待指定秒数，用于测试异步和timeout。",
    args_model=SleepArgs,
    handler=sleep_handle,
    timeout_seconds=1.0,
)


class DeleteFileArgs(BaseModel):
    """delete_file 工具入参: 目标文件路径(禁止额外字段)"""
    model_config = ConfigDict(extra="forbid")
    path: str    # 待删除的文件路径

def fake_delete_file(path: str) -> dict:
    """模拟删除文件(不真正操作磁盘)。
    参数 path: 文件路径
    返回: {"deleted": True, "path": path}
    """
    return {"deleted": True , "path": path}

delete_file_tool = Tool(
    name="delete_file",
    description="删除指定路径的文件，用于测试。",
    args_model=DeleteFileArgs,
    handler=fake_delete_file,
    required_permissions=frozenset({"file.delete"}),
    side_effects=True,
)

