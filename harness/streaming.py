# 文件：harness/streaming.py
"""Run 事件总线：把 Worker 侧的执行事实实时推给订阅者。

FastAPI 与 Durable Worker Pool 运行在同一个事件循环里，因此进程内的
asyncio.Queue 就足以完成推送，不需要引入消息中间件。Broker 同时为迟到的
订阅者保留一小段回放缓冲，这样“提交任务”和“打开流”之间的竞态不会丢事件。
"""
from __future__ import annotations

import asyncio
import inspect
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

# 只有这个事件代表 Run 不会再产生新事件，订阅者收到后即可关闭连接。
TERMINAL_EVENT = "run.end"


def accepts_keyword(function: Any, keyword: str) -> bool:
    """判断 Provider 的 generate() 是否接受某个关键字参数。

    Durable Worker 会在调用模型时补上 on_delta 回调；第三方 Provider 可能仍是
    旧签名，因此这里做一次签名探测，旧实现照常工作，只是没有增量输出。
    """
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False
    if keyword in parameters:
        return True
    return any(
        item.kind is inspect.Parameter.VAR_KEYWORD
        for item in parameters.values()
    )


class RunEventBroker:
    """按 run_id 广播事件，并保留最近若干次 Run 的完整回放。"""

    def __init__(
        self,
        *,
        retained_runs: int = 32,
        max_events_per_run: int = 20_000,
    ) -> None:
        self.retained_runs = retained_runs
        self.max_events_per_run = max_events_per_run
        self._buffers: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._sequences: dict[str, int] = {}

    def publish(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """追加事件并立即投递给所有在线订阅者（同步、不阻塞）。"""
        sequence = self._sequences.get(run_id, 0) + 1
        self._sequences[run_id] = sequence
        record = {"run_id": run_id, "seq": sequence, **event}

        buffer = self._buffers.setdefault(run_id, [])
        buffer.append(record)
        if len(buffer) > self.max_events_per_run:
            del buffer[: len(buffer) - self.max_events_per_run]
        self._buffers.move_to_end(run_id)
        while len(self._buffers) > self.retained_runs:
            evicted, _ = self._buffers.popitem(last=False)
            self._sequences.pop(evicted, None)

        for queue in tuple(self._subscribers.get(run_id, ())):
            queue.put_nowait(record)
        return record

    def open(
        self,
        run_id: str,
    ) -> tuple[asyncio.Queue, list[dict[str, Any]], Callable[[], None]]:
        """原子地返回「历史缓冲 + 后续事件队列 + 退订函数」。

        open() 内部没有 await，因此注册订阅者与读取缓冲之间既不会漏事件，
        也不会重复投递。
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(run_id, set()).add(queue)
        replay = list(self._buffers.get(run_id, ()))
        if run_id in self._buffers:
            self._buffers.move_to_end(run_id)

        def unsubscribe() -> None:
            subscribers = self._subscribers.get(run_id)
            if subscribers is None:
                return
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(run_id, None)

        return queue, replay, unsubscribe

    def has_finished(self, run_id: str) -> bool:
        return any(
            record.get("type") == TERMINAL_EVENT
            for record in self._buffers.get(run_id, ())
        )
