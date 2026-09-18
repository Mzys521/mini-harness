from dataclasses import dataclass , field
from typing import Any


# 工具调用
@dataclass
class ToolCall:
    """模型请求执行的一次工具调用"""
    call_id: str    # 本次调用的唯一ID，工具结果按此ID回传
    name: str       # 要调用的工具名
    arguments: dict[str , Any]    # 模型给出的工具参数(原始JSON对象)

@dataclass(frozen=True)
class ModelUsage:
    """统一 Provider Usage（供应商用量）模型。"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(self, other: "ModelUsage") -> "ModelUsage":
        return ModelUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )

@dataclass(frozen=True)
class ToolExecutionRecord:
    """Evaluation 需要的最小 Tool Execution Evidence（工具执行证据）。"""
    call_id: str
    name: str
    arguments: dict[str , Any]
    status: str 
    error_code : str | None = None


@dataclass
class RunEvidence:
    """与 OpenTelemetry（开放遥测）解耦的应用级运行事实。"""
    tool_executions: list[ToolExecutionRecord] = field(default_factory=list)
    model_usage: ModelUsage = field(default_factory=ModelUsage)


# 模型结果  
@dataclass
class ModelResult:
    """模型单次生成的结果"""
    text: str    # 模型输出的文本内容
    tool_calls: list[ToolCall] = field(default_factory=list)    # 模型请求的工具调用列表(可能为空)
    response_id : str | None = None    # 响应ID，用于下一轮请求续接上下文
    usage: ModelUsage = field(default_factory=ModelUsage)
    
@dataclass
class RunResult:
    """模型运行结果"""
    output: str
    steps: int
    response_id: str | None = None
    evidence: RunEvidence = field(default_factory=RunEvidence)


