"""app_tools/workspace.py：抽离到应用层的工作区工具。

这些工具不再依赖 DesktopService 或数据库——工作区根目录与知识库目录都来自
ToolContext，由服务端在提交 Run 时解析一次。
"""
import sys

import pytest

from app_tools.workspace import (
    tool_list,
    workspace_command,
    workspace_knowledge_search,
    workspace_list,
    workspace_read,
    workspace_write,
)
from harness.tools.definition import ToolContext


def make_context(tmp_path, *, with_knowledge=True):
    root = tmp_path / "project"
    root.mkdir()
    knowledge = tmp_path / "knowledge"
    if with_knowledge:
        knowledge.mkdir()
    context = ToolContext(
        run_id="run_test",
        workspace_id="ws_test",
        workspace_path=str(root),
        knowledge_path=str(knowledge) if with_knowledge else None,
    )
    return context, root, knowledge


def test_tool_list_declares_approval_and_context_injection():
    names = [tool.name for tool in tool_list]
    assert names == [
        "workspace_list",
        "workspace_read",
        "workspace_write",
        "workspace_command",
        "workspace_knowledge_search",
    ]
    assert all(tool.inject_context for tool in tool_list)
    approvable = {tool.name for tool in tool_list if tool.requires_approval and tool.side_effect}
    assert approvable == {"workspace_write", "workspace_command"}


def test_list_and_read_stay_inside_the_workspace(tmp_path):
    context, root, _ = make_context(tmp_path)
    (root / "pkg").mkdir()
    (root / "pkg" / "main.py").write_text("print('hello')", encoding="utf-8")

    listing = workspace_list(".", context=context)
    assert [entry["name"] for entry in listing["entries"]] == ["pkg"]
    nested = workspace_list("pkg", context=context)
    assert [entry["path"] for entry in nested["entries"]] == ["pkg/main.py"]
    assert workspace_read("pkg/main.py", context=context)["content"] == "print('hello')"


def test_paths_outside_the_workspace_are_rejected(tmp_path):
    context, root, _ = make_context(tmp_path)
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")

    with pytest.raises(ValueError):
        workspace_read("../secret.txt", context=context)
    with pytest.raises(ValueError):
        workspace_write(str(tmp_path / "secret.txt"), "overwritten", context=context)
    assert (tmp_path / "secret.txt").read_text(encoding="utf-8") == "top secret"


def test_write_returns_a_diff_and_creates_parent_directories(tmp_path):
    context, root, _ = make_context(tmp_path)
    (root / "main.py").write_text("before", encoding="utf-8")

    updated = workspace_write("main.py", "after", context=context)
    assert updated["diff"] == {"path": "main.py", "before": "before", "after": "after"}
    created = workspace_write("notes/todo.md", "- 写测试", context=context)
    assert created["diff"]["before"] == ""
    assert (root / "notes" / "todo.md").read_text(encoding="utf-8") == "- 写测试"


def test_command_runs_in_the_workspace_directory(tmp_path):
    context, root, _ = make_context(tmp_path)
    result = workspace_command([sys.executable, "-c", "import pathlib; print(pathlib.Path.cwd().name)"], context=context)
    assert result["exit_code"] == 0
    assert result["stdout"].strip() == "project"
    with pytest.raises(ValueError):
        workspace_command([], context=context)


def test_knowledge_search_reads_the_library_directory(tmp_path):
    context, _, knowledge = make_context(tmp_path)
    (knowledge / "doc_abc123_guide.md").write_text("部署流程：先跑迁移脚本再重启服务。", encoding="utf-8")
    (knowledge / "other.txt").write_text("无关内容", encoding="utf-8")
    (knowledge / "binary.bin").write_bytes(b"\x00\xff\xfe")

    result = workspace_knowledge_search("迁移脚本", context=context)
    assert result["total"] == 1
    assert result["matches"][0]["name"] == "guide.md"        # doc_id 前缀被去掉
    assert "迁移脚本" in result["matches"][0]["excerpt"]
    assert workspace_knowledge_search("不存在的词", context=context)["matches"] == []


def test_missing_workspace_context_fails_loudly(tmp_path):
    empty = ToolContext(run_id="run_test")
    with pytest.raises(ValueError):
        workspace_list(".", context=empty)

    context, _, _ = make_context(tmp_path, with_knowledge=False)
    assert workspace_knowledge_search("任意", context=context)["matches"] == []
