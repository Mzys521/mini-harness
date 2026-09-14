import os
import asyncio
import uuid
from dotenv import load_dotenv

from app_tools.demo_tools import delete_file_tool, sleep_tool 
from app_tools.calculator import calculator_tool , subtract_tool, multiply_tool, divide_tool

from harness.providers.openai_provider import OpenAIProvider
from harness.providers.deepseek_provider import DeepSeekProvider
from harness.runner import AgentRunner
from harness.tools.definition import ToolContext
from harness.tools.executor import ToolExecutor
from harness.tools.registry import ToolRegistry
from harness.tools.middleware import LoggingMiddleware

load_dotenv()

async def main() -> None:
    """示例入口: 组装工具注册表/执行器/模型/运行器，并运行一轮 Agent"""
    
    # 1. 注册所有工具
    registry = ToolRegistry()
    registry.register(calculator_tool)
    registry.register(sleep_tool)
    registry.register(delete_file_tool)
    registry.register(subtract_tool)
    registry.register(multiply_tool)
    registry.register(divide_tool)
    

    # 2. 创建工具执行器(挂载日志中间件)
    executor = ToolExecutor(
        registry=registry,
        middlewares=[LoggingMiddleware()]
    )

    # 3. 创建模型提供方(配置从 .env 读取)
    model = DeepSeekProvider(
        model= os.getenv("DEEPSEEK_MODEL"),
        api_key= os.getenv("DEEPSEEK_API_KEY"),
        base_url= os.getenv("DEEPSEEK_BASE_URL"),
    )

    # 4. 创建 Agent 运行器(最多 8 步)
    runner = AgentRunner(
        model=model,
        registry=registry,
        executor=executor,
        max_steps=8,
    )

    # 5. 构造工具执行上下文(含权限集合)
    context = ToolContext(
        run_id=str(uuid.uuid4()),
        user_id="user-001",
        tenant_id="tenant-001",
        permissions=frozenset({"calculator.use"})
    )

    # 6. 运行并打印最终结果
    result = await runner.run(
        "帮我计算 135.7 + 864.3 * 100  , 123.56 - 211.3 , 123.56 * 211.3 , 123.56 / 211.3 , 并将每个结果的和相加",
        context=context
    )

    print(result.output)    # 最终文本回复
    print("steps", result.steps)    # 消耗的步数

if __name__ == "__main__":
    asyncio.run(main())

