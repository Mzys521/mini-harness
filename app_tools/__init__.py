# 文件：app_tools/__init__.py
"""应用层工具包：所有工具都在这里定义，由应用入口统一注册。

分层约定（这条线不能反向跨越）：

    harness/     框架：工具运行时、注册表、审批、持久执行。**不 import app_tools**
    app_tools/   应用：具体工具实现。可以 import harness，但只用它的契约
                 （`Tool` / `tool_from_pydantic` / `ToolContext`）

`app_tools` 不随 mini-harness 发行版安装（见 pyproject 的 packages.find），
所以框架层任何 `from app_tools...` 都会让 `pip install mini-harness`
之后必然 ImportError；工具一律由应用入口（main.py）注册。

统一格式（对齐 calculator.py）：

    Pydantic 入参模型  →  普通函数（context 为关键字参数）  →  tool_from_pydantic
    模块底部导出 tool_list

需要运行时依赖（例如 RAG 检索管线）的工具用「工厂函数 + 参数注入」，
由组合根在依赖就绪后调用，不进入这里的 `tool_list`。
"""
from __future__ import annotations

from harness.tools.definition import Tool

from app_tools import calculator, notes, workspace


def all_tools() -> list[Tool]:
    """汇总本目录下所有「无运行时依赖」的工具。

    RAG（`app_tools.knowledge.build_search_knowledge_tool`）需要检索管线，
    MCP 工具来自远端，两者都由组合根单独注册，不在这里重复。
    """
    return [
        *calculator.tool_list,
        *notes.tool_list,
        *workspace.tool_list,
    ]


# 便于 `from app_tools import tool_list` 的旧写法。
tool_list = all_tools()

__all__ = ["all_tools", "tool_list", "calculator", "notes", "workspace"]
