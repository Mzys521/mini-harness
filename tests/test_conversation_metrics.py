"""用量在实时事件与持久化回放之间保持一致，缺失缓存数据不伪装成零。"""
import asyncio
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from harness.app.noop import NoopObservability
from harness.models import ModelResult, ModelUsage
from harness.providers.deepseek_provider import DeepSeekProvider
from harness.providers.openai_provider import OpenAIProvider
from tests.test_run_stream import build_app, prepare, read_stream


@pytest.mark.parametrize("cached", [None, 0, 80])
async def test_metrics_survive_stream_and_history(tmp_path, cached):
    model_elapsed: list[float] = []

    class Model:
        async def generate(self, **kwargs):
            started = perf_counter()
            await asyncio.sleep(.01)
            model_elapsed.append((perf_counter() - started) * 1000)
            return ModelResult(
                text="done", usage=ModelUsage(100, 20, 120, cached or 0),
                cache_usage_reported=cached is not None,
            )

    app = build_app(tmp_path, Model())
    api = await app.create_http_app()
    async with (
        api.router.lifespan_context(api),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api), base_url="http://local"
        ) as client,
    ):
        run_id = await prepare(client, tmp_path)
        events = await read_stream(client, run_id)
        metrics = next(e["metrics"] for e in events if e["type"] == "model.end")
        assert metrics["input_tokens"] == 100
        assert metrics["output_tokens"] == 20
        assert metrics["total_tokens"] == 120
        assert metrics["cached_input_tokens"] == cached
        # Runner 记录的是包住模型调用的墙钟时间，因此不会小于模型自测耗时。
        # 不假设 sleep(.01) 正好等于 10ms：Windows 上 asyncio 的定时器粒度粗于
        # perf_counter，实测会明显短于 10ms（本机约 3.7ms）。
        assert metrics["duration_ms"] >= model_elapsed[0] - 0.5
        assert metrics["context_window"] == 32_000
        trace = (await client.get(f"/v1/runs/{run_id}/trace")).json()
        node = next(n for n in trace["nodes"] if n["kind"] == "thought")
        assert node["metrics"] == metrics


@pytest.mark.parametrize("provider,field", [
    ("deepseek", "native"), ("deepseek", "compatible"),
    ("openai", "compatible"), ("deepseek", "missing"),
])
async def test_provider_cache_reporting(provider, field):
    async def chunks(item):
        yield item

    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120,
                            input_tokens=100, output_tokens=20)
    if field == "native":
        usage.prompt_cache_hit_tokens = 80
    elif field == "compatible":
        usage.prompt_tokens_details = SimpleNamespace(cached_tokens=80)
        usage.input_tokens_details = SimpleNamespace(cached_tokens=80)
    if provider == "deepseek":
        model = DeepSeekProvider(model="test", api_key="test-only",
                                 base_url="https://example.invalid")
        await model.client.close()
        chunk = SimpleNamespace(id="response", usage=usage, choices=[])
        model.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=AsyncMock(return_value=chunks(chunk)))))
    else:
        model = OpenAIProvider(model="test", api_key="test-only",
                               observability=NoopObservability())
        await model.client.close()
        response = SimpleNamespace(id="response", usage=usage, output=[], output_text="done")
        model.client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(
            return_value=chunks(SimpleNamespace(type="response.completed", response=response)))))
    result = await model.generate(input_data="hello", tools=[])
    assert result.cache_usage_reported is (field != "missing")
    assert result.usage.cached_input_tokens == (0 if field == "missing" else 80)
