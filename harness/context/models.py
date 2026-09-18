from dataclasses import dataclass , field
from enum import StrEnum
from typing import Any

class MessageRole(StrEnum):
    """消息角色"""
    SYSTEM = "system"    # 系统指令
    USER = "user"    # 用户
    ASSISTANT = "assistant"    # 模型
    TOOL = "tool"    # 工具结果


@dataclass(frozen=True)
class Message:
    """对话中的一条消息(不可变)"""
    role: MessageRole    # 角色
    content: str    # 文本内容
    metadata: dict[str,Any] =  field(default_factory=dict)    # 附加元数据(如 required/section，裁剪时使用)


@dataclass
class WorkingState:
    """Agent 的当前工作状态，注入上下文帮助模型保持目标感"""
    goal:str    # 当前目标
    facts:dict[str , Any] = field(default_factory=dict)    # 已确认的事实
    completed_steps: list[str] = field(default_factory=list)    # 已完成步骤
    pending_steps: list[str] = field(default_factory=list)    # 待完成步骤

@dataclass(frozen=True)
class ContextSection:
    """上下文中的一个片段(可裁剪单元)"""
    name: str    # 片段名(用于记录被丢弃的片段)
    priority: int    # 优先级(数值越大越重要)
    content: str    # 文本内容
    required: bool = False    # 是否必须保留(不可裁剪)

@dataclass(frozen=True)
class ModelContext:
    """构建完成、即将发送给模型的上下文"""
    instructions: str    # 指令
    input_data: list[dict[str , str]]    # 输入数据
    estimated_tokens: int    # 估算的 token 总数
    dropped_messages: int    # 被裁剪丢弃的消息数
    user_input: str    # 用户输入

# 在 0.6.0 版本中弃用
# @dataclass(frozen=True)
# class ModelContext:11                                                                                         ~~~ 
#     """构建完成、即将发送给模型的上下文"""
#     messages: list[Message]    # 最终消息列表
#     estimated_tokens: int    # 估算的 token 总数
#     dropped_sections: list[str]    # 被裁剪丢弃的片段名


