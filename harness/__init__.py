# 文件：harness/__init__.py
"""mini-harness public API.

普通开发者优先从这里导入；内部 Registry/Store/Manager 仍保留给高级扩展。
"""
# __version__ 必须在任何 harness.* 子模块导入之前定义：
# assembly.py 会 `from harness import __version__`，而这条导入链在包初始化
# 过程中就会触发，此时本模块尚未执行到下半部分。
__version__ = "0.14.0"

# 导入门面即加载 .env（不覆盖真实环境变量）。Phase 10 的教训：显式 load_dotenv()
# 一旦缺失，.env 会静默完全不生效；放在公共 API 入口可覆盖 HarnessApp() 直接构造的路径。
try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv 是声明依赖；缺失时不影响零配置启动
    pass
else:
    load_dotenv()

from harness.tools.definition import Tool, ToolContext
from harness.app import HarnessApp, HarnessConfig, HarnessPlugin, load_config, tool

__all__ = [
    "HarnessApp",
    "HarnessConfig",
    "HarnessPlugin",
    "Tool",
    "ToolContext",
    "load_config",
    "tool",
]
