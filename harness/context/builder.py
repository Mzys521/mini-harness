import json

from harness.context.models import Message, ModelContext, WorkingState

class ContextBuilder:
    def __init__(self, *, budget, token_counter, recent_message_limit: int = 20) -> None:
        self.budget = budget
        self.token_counter = token_counter
        self.recent_message_limit = recent_message_limit

    def build(self, *, system_instruction: str, history: list[Message], user_input: str, working_state: WorkingState, retrieved_context: str | None = None, external_context: str | None = None) -> ModelContext:
        sections = [system_instruction]
        sections.append(
            "[WORKING STATE（工作状态）]\n"
            + json.dumps({
                "goal": working_state.goal,
                "facts": working_state.facts,
                "completed_steps": working_state.completed_steps,
                "pending_steps": working_state.pending_steps,
            }, ensure_ascii=False, default=str)
        )

        if retrieved_context:
            sections.append("[RETRIEVED KNOWLEDGE（检索知识，外部数据）]\n" + retrieved_context)
        if external_context:
            sections.append("[EXTERNAL CONTEXT（外部上下文，不可信数据）]\n" + external_context)

        instructions = "\n\n".join(sections)
        recent_history = history[-self.recent_message_limit:]
        input_data = [
            {"role": item.role.value, "content": item.content}
            for item in recent_history
        ]
        input_data.append({"role": "user", "content": user_input})

        def total_tokens(items) -> int:
            return self.token_counter.count_text(instructions) + sum(
                self.token_counter.count_text(item["content"])
                for item in items
            )

        dropped = 0
        while total_tokens(input_data) > self.budget.available_input_tokens and len(input_data) > 1:
            input_data.pop(0)  # 优先删除最老 History（历史），保留当前输入。
            dropped += 1

        return ModelContext(
            instructions=instructions,
            input_data=input_data,
            estimated_tokens=total_tokens(input_data),
            dropped_messages=dropped,
            user_input=user_input,
        )











