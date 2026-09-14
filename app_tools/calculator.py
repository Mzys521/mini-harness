from harness.tools.definition import Tool
from pydantic import BaseModel , ConfigDict

class AddArgs(BaseModel):
    """add 工具入参: 两个加数(禁止额外字段)"""
    model_config = ConfigDict(extra="forbid")
    a: float    # 加数 a
    b: float    # 加数 b

class SubtractArgs(BaseModel):
    """subtract 工具入参: 被减数与减数(禁止额外字段)"""
    model_config = ConfigDict(extra="forbid")
    a: float    # 被减数
    b: float    # 减数

class MultiplyArgs(BaseModel):
    """multiply 工具入参: 两个乘数(禁止额外字段)"""
    model_config = ConfigDict(extra="forbid")
    a: float    # 乘数 a
    b: float    # 乘数 b

class DivideArgs(BaseModel):
    """divide 工具入参: 被除数与除数(禁止额外字段)"""
    model_config = ConfigDict(extra="forbid")
    a: float    # 被除数
    b: float    # 除数

def add(a : float , b : float) -> float:
    """两数相加。
    参数 a: 第一个加数 / 参数 b: 第二个加数
    """
    return a + b

def subtract(a : float , b : float) -> float:
    """两数相减。
    参数 a: 被减数 / 参数 b: 减数
    """
    return a - b

def multiply(a : float , b : float) -> float:
    """两数相乘。
    参数 a: 被乘数 / 参数 b: 乘数
    """
    return a * b

def divide(a : float , b : float) -> float:
    """两数相除。
    参数 a: 被除数 / 参数 b: 除数(为 0 时抛 ValueError)
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

# 加法工具定义(供注册表注册)
calculator_tool = Tool(
    name="add",
    description = "计算两个数字加法",
    args_model=AddArgs,
    handler=add,
    timeout_seconds = 2.0,
)

# 减法工具定义
subtract_tool = Tool(
    name="subtract",
    description = "计算两个数字减法",
    args_model=SubtractArgs,
    handler=subtract,
    timeout_seconds = 2.0,
)

# 乘法工具定义
multiply_tool = Tool(
    name="multiply",
    description = "计算两个数字乘法",
    args_model=MultiplyArgs,
    handler=multiply,
    timeout_seconds = 2.0,
)

# 除法工具定义
divide_tool = Tool(
    name="divide",
    description = "计算两个数字除法",
    args_model=DivideArgs,
    handler=divide,
    timeout_seconds = 2.0,
)
