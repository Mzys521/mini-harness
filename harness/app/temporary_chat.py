"""Temporary chat owns only volatile state: no database, broker or audit sink."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from time import monotonic
from typing import Any
from uuid import uuid4

from harness.context.models import Message, MessageRole
from harness.tools.definition import ToolContext


@dataclass
class TemporaryConversation:
    history: list = field(default_factory=list)
    touched: float = field(default_factory=monotonic)
    task: asyncio.Task | None = None


class TemporaryChats:
    ttl = 1800

    def __init__(self, runner: Any, personal: Any):
        self.runner, self.personal = runner, personal
        self.sessions: dict[str, TemporaryConversation] = {}
        self.queues: dict[str, asyncio.Queue] = {}

    def emit(self, run_id: str, event: dict) -> None:
        if run_id in self.queues:
            self.queues[run_id].put_nowait(event)

    def create(self) -> dict:
        self.expire()
        if len(self.sessions) >= 100:
            raise ValueError('临时对话数量已达上限，请结束不用的对话')
        sid = f'temp_{uuid4().hex}'
        self.sessions[sid] = TemporaryConversation()
        return {'id': sid}

    def end(self, sid: str) -> None:
        session = self.sessions.pop(sid, None)
        if session:
            if session.task:
                session.task.cancel()
            session.history.clear()

    def expire(self) -> None:
        for sid, session in list(self.sessions.items()):
            if monotonic() - session.touched > self.ttl:
                self.end(sid)

    async def cleanup(self, stop_event: asyncio.Event) -> None:
        try:
            while not stop_event.is_set():
                self.expire()
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=30)
                except TimeoutError:
                    pass
        finally:
            tasks = [session.task for session in self.sessions.values() if session.task]
            for sid in list(self.sessions):
                self.end(sid)
            await asyncio.gather(*tasks, return_exceptions=True)

    def stream(self, sid: str, text: str, skill_ids: list[str]):
        self.expire()
        session = self.sessions.get(sid)
        if session is None:
            raise LookupError('临时对话已结束或过期，请重新开始')
        if session.task:
            raise ValueError('上一条消息仍在生成')
        context = self.personal.context(skill_ids)
        run_id = f'tmp_run_{uuid4().hex}'
        queue: asyncio.Queue = asyncio.Queue()
        self.queues[run_id] = queue
        session.touched = monotonic()

        async def generate():
            try:
                async with asyncio.timeout(180):
                    result = await self.runner.run(text, history=session.history,
                        tool_context=ToolContext(run_id=run_id, tool_names=frozenset()),
                        external_context=context + '\n临时对话：只回答，不保存新的习惯或长期记忆，不执行工具。')
                session.history.extend([Message(role=MessageRole.USER, content=text), Message(role=MessageRole.ASSISTANT, content=result.output)])
                session.history[:] = session.history[-20:]
                queue.put_nowait({'type': 'run.end', 'output': result.output})
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - do not expose provider exceptions or prompt contents
                # Do not serialize provider errors (they may contain prompt text).
                queue.put_nowait({'type': 'error', 'message': '临时对话生成失败，请重试。'})
            finally:
                queue.put_nowait(None)

        session.task = asyncio.create_task(generate())

        async def events():
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield 'data: ' + json.dumps(item, ensure_ascii=False) + '\n\n'
            finally:
                task = session.task
                if task and not task.done():
                    task.cancel()
                    self.end(sid)
                if task:
                    await asyncio.gather(task, return_exceptions=True)
                session.task = None
                session.touched = monotonic()
                self.queues.pop(run_id, None)

        return events()
