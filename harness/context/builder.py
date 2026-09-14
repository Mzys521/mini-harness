from harness.context.budget import TokenBudget , TokenCounter
from harness.context.models import (
    Message,
    MessageRole,
    ModelContext,
    WorkingState,
)
from harness.context.policy import ContextPolicy
from harness.context.sources import (
    select_recent_messages,
    working_state_section,
)
from harness.tools.errors import ToolNotFoundError

# 上下文构建器
class ContextBuilder:
    """按预算与策略组装模型上下文: 系统指令 + 工作状态 + 最近历史 + 当前输入，并裁剪超预算内容"""

    def __init__(self, * , budget: TokenBudget , token_counter: TokenCounter , policy: ContextPolicy):
        """初始化构建器。
        参数 budget: token 预算
        参数 token_counter: token 计数器
        参数 policy: 上下文策略
        """
        self.budget = budget    # Token 预算
        self.token_counter = token_counter    # Token 计数器
        self.policy = policy    # 上下文策略
        
    def build(self, * , system_instruction: list[Message] , history: list[Message] , current_user_input:  str , working_state: WorkingState | None = None) -> ModelContext:
        """组装一份模型上下文。
        参数 system_instruction: 系统指令(最高优先级，必保留)
        参数 history: 历史消息列表(按策略截取最近部分)
        参数 current_user_input: 当前用户输入(必保留)
        参数 working_state: 可选工作状态，按 policy 决定是否注入
        返回: ModelContext(含估算 token 与已丢弃片段)
        """

        messages: list[Message] = []
        dropped_sections: list[str] = []

        # System instruction 属于最高优先级信息
        messages.append(
            Message(
                role=MessageRole.SYSTEM,
                content=system_instruction,
                metadata={
                    "required" : True,
                    "section" : "system",
                },
            ),
        )

        # 按 Policy 决定是否注入Working State
        if (working_state is not None and self.policy.include_working_state):
            section = working_state_section(working_state)

            messages.append(
                Message(
                    role=MessageRole.SYSTEM,
                    content=("[WORKING STATE]\n" + section.content),
                    metadata={
                        "section" : section.name,
                        "priority" : section.priority,
                    },
                )
            )

        # todo(替换SlidingWindows)
        # 先使用 Sliding Window
        recent_history = select_recent_messages(history , self.policy.recent_messages_limit)
        messages.extend(recent_history)

        # 当前用户输入必须注入
        messages.append(
            Message(
                role=MessageRole.USER,
                content=current_user_input,
                metadata={
                    "required" : True,
                    "section" : "current_user_input",
                },
            )
        )

        # 根据 Token Budge 进行裁剪
        messages = self._fit_budget(messages , dropped_sections)

        # 重新估算最终上下文的 token 数
        estimated_tokens = sum(self.token_counter.count_text(x.content) for x in messages)

        return ModelContext(
            messages = messages,
            estimated_tokens = estimated_tokens,
            dropped_sections = dropped_sections,
        )

    # 根据 Token Budget 进行裁剪
    def _fit_budget(self, messages: list[Message] , dropped_sections: list[str],) -> list[Message]:
        """不断移除最老的可裁剪消息，直到 token 估算不超预算。
        参数 messages: 待裁剪消息列表
        参数 dropped_sections: 被丢弃片段名的收集列表(原地追加)
        返回: 裁剪后的消息列表
        """
        result = list(messages)
        available = self.budget.available_input_tokens

        def count(items : list[Message]) -> int:
            """统计一组消息的 token 数。参数 items: 消息列表"""
            return sum(self.token_counter.count_text(x.content) for x in items)
        
        while count(result) > available:
            removeable_index = (self._find_oldest_removable(result))
            if removeable_index is None:
                break

            removed = result.pop(removeable_index)

            dropped_sections.append(
                removed.metadata.get(
                    "section",
                    removed.role.value,
                ),
            )
        
        return result

    # 找到最老的可移除的消息
    def _find_oldest_removable(self, messages: list[Message]) -> int | None:
        """找到第一个可移除消息的下标(跳过 required 的消息)。
        参数 messages: 消息列表
        返回: 可移除消息的下标；全部必须保留时返回 None
        """

        for index , message in enumerate(messages):
            if message.metadata.get("required") :
                continue
            return index
        return None















