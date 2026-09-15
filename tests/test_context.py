import pytest

from harness.context import builder
from harness.context import budget
from harness.context.budget import (
    ApproxTokenCounter,
    TokenBudget,
)

from harness.context.builder import ContextBuilder
from harness.context.models import(
    Message, 
    MessageRole,
    WorkingState,
)
from harness.context.policy import ContextPolicy


# 测试当前输入是否被保留
def test_current_input_is_kept():
    """构建上下文后，消息列表中应包含当前用户输入。"""
    builder = ContextBuilder(
        budget = TokenBudget(
            max_context_tokens= 1000,
            reserved_output_tokens= 256,
        ),

        token_counter= ApproxTokenCounter(),
        policy= ContextPolicy(),
    )

    context = builder.build(
        system_instruction= "You are a helpful assistant." ,  # 系统prompt
        history= [],
        current_user_input= "important request",
    )

    assert any(
        x.content == "important request" for x in context.messages
    )

# 测试历史记录是否被截断
def test_history_limit():
    """限制 recent_messages_limit=5 时，只保留最近消息，旧消息被丢弃。"""
    # 创建一个包含20条消息的历史记录
    history = [Message(role=MessageRole.USER , content =f"message-{i}") for i in range(20)]

    builder = ContextBuilder(
        budget=TokenBudget(
            max_context_tokens=10000,
            reserved_output_tokens=256,
        ),

        token_counter= ApproxTokenCounter() , # Token 计数器
        policy=ContextPolicy( recent_messages_limit=5),
    )

    context = builder.build(
        system_instruction= "system",
        history= history,
        current_user_input= "current",
    )

    contents = [x.content for x in context.messages]

    assert "message-19" in contents
    assert "message-0" not in contents

# 测试上下文是否遵守预算
def test_context_respects_budget():
    """超小预算下，估算 token 不超可用输入上限，且有片段被裁剪。"""
    history=[Message(role=MessageRole.USER , content ="x" * 500) for _ in range(20)]
    
    budget = TokenBudget(
        max_context_tokens=500,
        reserved_output_tokens=100,
        safety_margin_tokens=50,
    )

    builder = ContextBuilder(
        budget=budget,
        token_counter=ApproxTokenCounter(),
        policy=ContextPolicy(recent_messages_limit=20),
    )

    context = builder.build(
        system_instruction="system",
        history=history,
        current_user_input="current",
    )

    # 确保上下文的Token数不超过预算
    assert (context.estimated_tokens <= budget.available_input_tokens)
    # 确保有部分消息被 dropped
    assert (context.dropped_sections)

# working State 注入
def test_working_state_is_included():
    """传入 working_state 时，其内容应被注入上下文。"""
    builder = ContextBuilder(
        budget= TokenBudget(
            max_context_tokens=5000,
            reserved_output_tokens=500,
        ),        
        token_counter= ApproxTokenCounter(),
        policy=ContextPolicy(),
    )

    state = WorkingState(
        goal="build harness",
        completed_steps=["step tool runtime"],  # 已完成的步骤
        pending_steps=["context engineering"],  # 待完成的步骤
    )

    context = builder.build(
        system_instruction="system",
        history =[],
        current_user_input="continue",
        working_state=state,
    )

    assert any("build harness" in x.content for x in context.messages)








