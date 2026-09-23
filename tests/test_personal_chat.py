"""Real HTTP, durable execution and non-retention boundaries; no remote model calls."""
import asyncio
from datetime import UTC, datetime, timedelta

from harness.app.personal import AutomationInput
from harness.models import ToolCall
from tests.test_desktop_api import ScriptedModel, run_worker, setup_app, workspace


def future():
    return (datetime.now(UTC) + timedelta(hours=1)).isoformat()


def test_normal_chat_preferences_skills_and_workspace_isolation(tmp_path):
    model = ScriptedModel()
    app, client = setup_app(tmp_path, model)
    assert client.put('/v1/preferences', json={'content': '默认中文，先结论'}).status_code == 200
    skill = client.post('/v1/skills/import', json={'document': '---\nname: editor\ndescription: >\n  简明\n  编辑\n---\n请以编辑身份回答。'}).json()
    assert skill['description'].strip() == '简明 编辑'
    session = client.post('/v1/sessions', json={'title': '普通对话'}).json()
    assert session['workspace_id'] == ''
    submitted = client.post('/v1/runs', json={'input': '你好', 'conversation_id': session['id'], 'skill_ids': [skill['id']]})
    assert submitted.status_code == 202, submitted.text
    run_worker(app)
    assert '默认中文，先结论' in model.instructions[-1]
    assert '请以编辑身份回答' in model.instructions[-1]
    record = app.runtime.durable_store.get(submitted.json()['run_id'])
    assert record.execution.tool_context.tool_names == frozenset({'create_scheduled_task', 'remember_user_preference'})
    w = workspace(client, tmp_path / 'project')
    assert client.post('/v1/runs', json={'input': '越界', 'conversation_id': session['id'], 'workspace_id': w['id']}).status_code == 400
    assert client.get('/v1/sessions', params={'workspace_id': w['id']}).json()['items'] == []
    assert client.get('/v1/sessions').json()['items'][0]['id'] == session['id']
    assert client.patch(f"/v1/sessions/{session['id']}", json={'archived': True}).status_code == 200
    assert client.get('/v1/sessions').json()['items'] == []
    assert client.get('/v1/sessions?archived=true').json()['items'][0]['id'] == session['id']
    assert client.delete(f"/v1/sessions/{session['id']}").status_code == 200
    _, reopened = setup_app(tmp_path)
    assert reopened.get('/v1/preferences').json()['content'] == '默认中文，先结论'
    assert reopened.get('/v1/skills').json()['items'][0]['id'] == skill['id']


def test_skills_validation_and_disabled_skill_cannot_be_used(tmp_path):
    _, client = setup_app(tmp_path)
    for document in ['plain body', '---\nname: missing-body\n---', '---\nname: unfinished']:
        assert client.post('/v1/skills/import', json={'document': document}).status_code in {400, 422}
    skill = client.post('/v1/skills', json={'name': '技能', 'instructions': '简洁回答'}).json()
    assert client.put(f"/v1/skills/{skill['id']}", json={'name': '技能', 'instructions': '简洁回答', 'enabled': False}).status_code == 200
    assert client.post('/v1/runs', json={'input': '你好', 'skill_ids': [skill['id']]}).status_code == 400
    assert client.get('/v1/sessions').json()['items'] == []
    assert client.delete(f"/v1/skills/{skill['id']}").status_code == 200
    assert client.get('/v1/skills').json()['items'] == []


def test_project_chat_discovers_created_knowledge_repositories(tmp_path):
    from types import SimpleNamespace

    model = ScriptedModel()
    app, client = setup_app(tmp_path, model)
    app.runtime.knowledge = SimpleNamespace(get_repositories=lambda: [SimpleNamespace(id='kr_docs', name='开发文档')])
    project = workspace(client, tmp_path / 'project')
    response = client.post('/v1/runs', json={'input': '从开发文档中查找答案', 'workspace_id': project['id']})
    assert response.status_code == 202
    run_worker(app)
    assert 'kr_docs' in model.instructions[-1]
    assert '开发文档' in model.instructions[-1]


def test_manual_scheduling_persists_claims_once_and_shows_deleted_result(tmp_path):
    app, client = setup_app(tmp_path)
    task = client.post('/v1/automations', json={'name': '提醒', 'prompt': '整理今天的目标', 'run_at': future()}).json()
    assert task['enabled'] == 1
    assert client.post('/v1/automations', json={'name': '无时区', 'prompt': '目标', 'run_at': '2099-01-01T10:00:00'}).status_code == 400
    assert client.post('/v1/automations', json={'name': '过快', 'prompt': '目标', 'run_at': future(), 'interval_seconds': 1}).status_code == 400
    app.runtime.personal.store.execute('UPDATE personal_automations SET next_run=? WHERE id=?', ((datetime.now(UTC)-timedelta(seconds=1)).isoformat(), task['id']))
    asyncio.run(app.runtime.scheduler.tick())
    asyncio.run(app.runtime.scheduler.tick())
    items = client.get('/v1/automations').json()['items']
    assert items[0]['enabled'] == 0
    assert items[0]['last_status'] == 'submitted'
    assert len(client.get('/v1/sessions').json()['items']) == 1
    run_worker(app)
    sid = items[0]['last_session_id']
    assert client.delete(f'/v1/sessions/{sid}').status_code == 200
    assert client.get('/v1/automations').json()['items'][0]['run_status'] == 'removed'
    _, reopened = setup_app(tmp_path)
    assert reopened.get('/v1/automations').json()['items'][0]['id'] == task['id']


def test_recurring_schedule_coalesces_missed_intervals_and_pauses(tmp_path):
    app, client = setup_app(tmp_path)
    task = app.runtime.personal.create_automation(AutomationInput(name='重复', prompt='总结', run_at=future(), interval_seconds=60))
    old = (datetime.now(UTC)-timedelta(hours=2)).isoformat()
    app.runtime.personal.store.execute('UPDATE personal_automations SET next_run=? WHERE id=?', (old, task['id']))
    asyncio.run(app.runtime.scheduler.tick())
    item = app.runtime.personal.get_automations()[0]
    assert datetime.fromisoformat(item['next_run']) > datetime.now(UTC)
    asyncio.run(app.runtime.scheduler.tick())
    assert len(client.get('/v1/sessions').json()['items']) == 1
    assert client.patch(f"/v1/automations/{task['id']}", json={'enabled': False}).status_code == 200
    app.runtime.personal.store.execute('UPDATE personal_automations SET next_run=? WHERE id=?', (old, task['id']))
    asyncio.run(app.runtime.scheduler.tick())
    assert len(client.get('/v1/sessions').json()['items']) == 1


def test_conversation_schedule_requires_approval(tmp_path):
    model = ScriptedModel([ToolCall(call_id='schedule', name='create_scheduled_task', arguments={'name': '明天的目标', 'prompt': '整理目标', 'run_at': future()})])
    app, client = setup_app(tmp_path, model)
    submitted = client.post('/v1/runs', json={'input': '一小时后帮我整理目标'}).json()
    run_worker(app)
    assert app.runtime.personal.get_automations() == []
    assert client.post(f"/v1/runs/{submitted['run_id']}/approve").status_code == 202
    run_worker(app)
    assert len(app.runtime.personal.get_automations()) == 1


def test_temporary_uses_preferences_without_persistence_or_shared_events(tmp_path):
    model = ScriptedModel()
    app, client = setup_app(tmp_path, model)
    client.put('/v1/preferences', json={'content': '习惯只读标记'})
    before = {row['name']: app.runtime.desktop.rows(f"SELECT COUNT(*) AS n FROM [{row['name']}]")[0]['n']
              for row in app.runtime.desktop.rows("SELECT name FROM sqlite_master WHERE type='table'")}
    sid = client.post('/v1/temporary-chats').json()['id']
    result = client.post(f'/v1/temporary-chats/{sid}/messages', json={'input': '临时秘密标记'})
    assert result.status_code == 200, result.text
    assert result.headers['cache-control'] == 'no-store'
    assert '已完成' in result.text
    assert '习惯只读标记' in model.instructions[-1]
    assert len(app.runtime.temporary.sessions[sid].history) == 2
    assert app.runtime.temporary.queues == {}
    for table, count in before.items():
        assert app.runtime.desktop.rows(f'SELECT COUNT(*) AS n FROM [{table}]')[0]['n'] == count
    assert not (tmp_path / 'audit.jsonl').exists()
    assert client.post(f'/v1/temporary-chats/{sid}/end').status_code == 200
    assert sid not in app.runtime.temporary.sessions
    assert client.post(f'/v1/temporary-chats/{sid}/messages', json={'input': '不能续聊'}).status_code == 404
    assert app.runtime.personal.get_preferences() == '习惯只读标记'
    sid = app.runtime.temporary.create()['id']
    app.runtime.temporary.sessions[sid].touched -= 1801
    app.runtime.temporary.expire()
    assert sid not in app.runtime.temporary.sessions


async def test_temporary_disconnect_cancels_generation_and_clears_memory(tmp_path):
    from harness.app.temporary_chat import TemporaryChats

    class Personal:
        def context(self, ids):
            return ''

    started = asyncio.Event()

    class Runner:
        async def run(self, text, **kwargs):
            temp.emit(kwargs['tool_context'].run_id, {'type': 'model.start'})
            started.set()
            await asyncio.Event().wait()

    temp = TemporaryChats(Runner(), Personal())
    sid = temp.create()['id']
    stream = temp.stream(sid, '不要保存', [])
    await anext(stream)
    await started.wait()
    task = temp.sessions[sid].task
    await stream.aclose()
    assert task.cancelled()
    assert temp.sessions == {}
    assert temp.queues == {}


async def test_private_provider_adapters_disable_response_retention():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from harness.app.noop import NoopObservability
    from harness.providers.deepseek_provider import DeepSeekProvider
    from harness.providers.openai_provider import OpenAIProvider

    async def chunks(item):
        yield item

    response = SimpleNamespace(id='private-response', output_text='答复', output=[], usage=None)
    create_openai = AsyncMock(return_value=chunks(SimpleNamespace(type='response.completed', response=response)))
    openai = OpenAIProvider(model='test', observability=NoopObservability(), api_key='test-only')
    await openai.client.close()
    openai.client = SimpleNamespace(responses=SimpleNamespace(create=create_openai))
    openai.store_responses = False
    assert (await openai.generate(input_data='私密', tools=[])).text == '答复'
    assert create_openai.call_args.kwargs['store'] is False

    chunk = SimpleNamespace(id='private-response', usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content='答复', tool_calls=[]))])
    create_deepseek = AsyncMock(return_value=chunks(chunk))
    deepseek = DeepSeekProvider(model='test', api_key='test-only', base_url='https://example.invalid')
    await deepseek.client.close()
    deepseek.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_deepseek)))
    deepseek.store_responses = False
    assert (await deepseek.generate(input_data='私密', tools=[])).text == '答复'
    assert deepseek._histories == {}
