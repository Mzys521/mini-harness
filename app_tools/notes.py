# 文件：app_tools/notes.py
import json
from pathlib import Path
from threading import Lock

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from harness.tools.factory import (
    tool_from_pydantic,
)

_NOTES_PATH = Path(
    "data/demo_notes.jsonl"
)
_NOTES_LOCK = Lock()

class CreateNoteArgs(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )
    title: str = Field(
        min_length=1,
        max_length=100,
    )
    body: str = Field(
        min_length=1,
        max_length=2_000,
    )

def create_note(
    title: str,
    body: str,
) -> dict:
    """真正产生本地文件副作用，用于验证 Approval Gate。"""
    _NOTES_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "title": title,
        "body": body,
    }

    with _NOTES_LOCK:
        with _NOTES_PATH.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                )
                + "\n"
            )

    return {
        "created": True,
        "title": title,
    }

create_note_tool = (
    tool_from_pydantic(
        name="create_note",
        description=(
            "把一条演示笔记写入本地 Note Store。"
            "这是具有副作用的 Tool。"
        ),
        args_model=CreateNoteArgs,
        handler=create_note,
        timeout_seconds=3.0,
        max_retries=0,
        required_permissions=frozenset({
            "note.create"
        }),
        side_effect=True,
        source="local",
    )
)