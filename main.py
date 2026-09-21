# 文件：main.py
from app_tools import all_tools

from harness import HarnessApp

# 开源默认入口只做三件事：加载配置、注册项目工具、运行 CLI。
# 工具全部定义在 app_tools/（每个模块按 calculator.py 的格式导出 tool_list），
# 这里一次性注册；框架内部不再内置任何业务工具。
app = HarnessApp.from_toml("harness.toml", optional=True)
app.add_tools(all_tools())

if __name__ == "__main__":
    app.cli()
