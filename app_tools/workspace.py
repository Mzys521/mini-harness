# 文件：app_tools/workspace.py
"""工作区工具：把用户选择的本地目录当成 Agent 的操作沙箱。

格式与 `calculator.py` 保持一致：每个工具都是「Pydantic 入参模型 + 普通函数 +
`tool_from_pydantic(...)`」，模块底部导出 `tool_list`。

工作区根目录来自 `ToolContext.workspace_path`（服务端在提交 Run 时解析一次），
所以这里既不需要数据库，也不需要服务实例，更不需要框架反向 import 本包。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from harness.tools.definition import ToolContext
from harness.tools.factory import tool_from_pydantic


MAX_FILE_BYTES = 2_000_000
MAX_ENTRIES = 500
COMMAND_TIMEOUT_SECONDS = 60.0
KNOWLEDGE_EXCERPT_CHARS = 1_200


def _workspace_root(context: ToolContext) -> Path:
    if not context.workspace_path:
        raise ValueError("请先选择工作区后再启动任务")
    return Path(context.workspace_path).expanduser().resolve()


def _resolve(root: Path, relative: str) -> Path:
    """把相对路径解析到工作区内；越界（../ 或绝对路径）直接拒绝。"""
    candidate = (root / (relative or ".")).expanduser().resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise ValueError("路径必须位于所选工作区内")
    return candidate


def _relative(root: Path, target: Path) -> str:
    return str(target.relative_to(root)).replace("\\", "/") or "."


# --------------------------------------------------------------------------- list

class WorkspaceListArgs(BaseModel):
    """workspace_list 入参。"""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(default=".", description="相对工作区根目录的目录路径")


def workspace_list(path: str, *, context: ToolContext) -> dict:
    """列出工作区内某个目录下的文件与子目录。"""
    root = _workspace_root(context)
    folder = _resolve(root, path)
    if not folder.is_dir():
        raise ValueError(f"目录不存在：{path}")

    entries = []
    for item in sorted(folder.iterdir(), key=lambda node: (not node.is_dir(), node.name.lower())):
        if item.name == ".git":
            continue
        try:
            resolved = item.resolve()
            if not resolved.is_relative_to(root):
                continue
        except OSError:
            continue
        entries.append({"name": item.name, "path": _relative(root, resolved), "directory": item.is_dir()})
        if len(entries) >= MAX_ENTRIES:
            break

    return {"path": _relative(root, folder), "entries": entries}


# --------------------------------------------------------------------------- read

class WorkspaceReadArgs(BaseModel):
    """workspace_read 入参。"""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, description="相对工作区根目录的文件路径")


def workspace_read(path: str, *, context: ToolContext) -> dict:
    """读取工作区内的 UTF-8 文本文件。"""
    root = _workspace_root(context)
    target = _resolve(root, path)
    if not target.is_file():
        raise ValueError(f"文件不存在：{path}")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("该文件超过 2 MB，请先用命令或编辑器在本地查看")
    return {"path": path, "content": target.read_text(encoding="utf-8-sig")}


# --------------------------------------------------------------------------- write

class WorkspaceWriteArgs(BaseModel):
    """workspace_write 入参。"""

    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, description="相对工作区根目录的文件路径")
    content: str = Field(description="写入的完整文本内容（会覆盖原文件）")


def workspace_write(path: str, content: str, *, context: ToolContext) -> dict:
    """写入工作区文件，返回修改前后的 diff。"""
    root = _workspace_root(context)
    target = _resolve(root, path)
    if target.is_dir():
        raise ValueError(f"目标是一个目录：{path}")
    before = target.read_text(encoding="utf-8") if target.exists() else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"diff": {"path": path, "before": before, "after": content}}


# --------------------------------------------------------------------------- command

class WorkspaceCommandArgs(BaseModel):
    """workspace_command 入参。"""

    model_config = ConfigDict(extra="forbid")
    argv: list[str] = Field(
        min_length=1,
        description="命令与参数数组，例如 ['python', '-m', 'pytest', '-q']；不走 shell，无需转义",
    )


def workspace_command(argv: list[str], *, context: ToolContext) -> dict:
    """在工作区目录里执行一条命令（参数数组，shell=False）。"""
    if not argv:
        raise ValueError("命令参数不能为空")
    root = _workspace_root(context)
    result = subprocess.run(
        argv,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=COMMAND_TIMEOUT_SECONDS,
        shell=False,
    )
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


# --------------------------------------------------------------------------- knowledge

class WorkspaceKnowledgeSearchArgs(BaseModel):
    """workspace_knowledge_search 入参。"""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200, description="关键词或短语")


def workspace_knowledge_search(query: str, *, context: ToolContext) -> dict:
    """在工作区知识库目录里做关键词检索，返回命中文件名与上下文片段。

    直接读目录而不是查数据库：知识库文件由工作区上传接口写入该目录，
    这样工具层保持纯文件系统语义，不需要知道存储实现。
    """
    if not context.knowledge_path:
        return {"query": query, "matches": [], "note": "当前工作区没有配置知识库目录"}

    library = Path(context.knowledge_path).expanduser().resolve()
    if not library.is_dir():
        return {"query": query, "matches": [], "note": "知识库目录还不存在，请先上传资料"}

    needle = query.lower()
    matches = []
    for item in sorted(library.rglob("*")):
        if not item.is_file() or item.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = item.read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError):
            continue          # 二进制或不可读文件直接跳过
        offset = text.lower().find(needle)
        if offset < 0:
            continue
        # 上传时文件名是 `{doc_id}_{原文件名}`，其中 doc_id 形如 `doc_<hex>`，展示时去掉前缀。
        parts = item.name.split("_", 2)
        name = parts[2] if item.name.startswith("doc_") and len(parts) == 3 else item.name
        start = max(0, offset - 200)
        matches.append({
            "name": name,
            "path": str(item),
            "excerpt": text[start:start + KNOWLEDGE_EXCERPT_CHARS],
        })

    return {"query": query, "matches": matches[:10], "total": len(matches)}


# --------------------------------------------------------------------------- 注册

workspace_list_tool = tool_from_pydantic(
    name="workspace_list",
    description="列出当前工作区相对路径下的文件与目录",
    args_model=WorkspaceListArgs,
    handler=workspace_list,
    timeout_seconds=10.0,
    source="workspace",
    inject_context=True,
)

workspace_read_tool = tool_from_pydantic(
    name="workspace_read",
    description="读取当前工作区内的 UTF-8 文本文件（单文件上限 2 MB）",
    args_model=WorkspaceReadArgs,
    handler=workspace_read,
    timeout_seconds=10.0,
    source="workspace",
    inject_context=True,
)

workspace_write_tool = tool_from_pydantic(
    name="workspace_write",
    description="写入工作区文件（覆盖原内容）。须人工批准，返回修改前后的 diff",
    args_model=WorkspaceWriteArgs,
    handler=workspace_write,
    timeout_seconds=10.0,
    side_effect=True,
    requires_approval=True,
    source="workspace",
    inject_context=True,
)

workspace_command_tool = tool_from_pydantic(
    name="workspace_command",
    description=(
        "在工作区目录执行命令参数数组（shell=False，无需转义），须人工批准。"
        f"适合测试、构建、git 状态；超时 {int(COMMAND_TIMEOUT_SECONDS)} 秒"
    ),
    args_model=WorkspaceCommandArgs,
    handler=workspace_command,
    timeout_seconds=COMMAND_TIMEOUT_SECONDS + 5,
    side_effect=True,
    requires_approval=True,
    source="workspace",
    inject_context=True,
)

workspace_knowledge_search_tool = tool_from_pydantic(
    name="workspace_knowledge_search",
    description="在用户为本工作区上传的知识库资料里做关键词检索",
    args_model=WorkspaceKnowledgeSearchArgs,
    handler=workspace_knowledge_search,
    timeout_seconds=10.0,
    source="workspace",
    inject_context=True,
)

tool_list = [
    workspace_list_tool,
    workspace_read_tool,
    workspace_write_tool,
    workspace_command_tool,
    workspace_knowledge_search_tool,
]
