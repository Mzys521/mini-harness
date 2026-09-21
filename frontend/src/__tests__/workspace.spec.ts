import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { nextTick } from 'vue';
import App from '@/App.vue';
import MarkdownText from '@/components/MarkdownText.vue';
import { useChat, turnFromRun } from '@/stores/chat';
import { APPEARANCE_KEY } from '@/stores/appearance';

/** Minimal EventSource double: records instances and lets a test push frames. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;

  readonly url: string;
  readyState = FakeEventSource.OPEN;
  onmessage: ((message: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  emit(event: unknown): void {
    this.onmessage?.({ data: JSON.stringify(event) });
  }

  close(): void {
    this.readyState = FakeEventSource.CLOSED;
  }
}

const workspace = { id: 'ws_1', name: 'demo', path: 'E:/project/demo', knowledge_path: 'E:/project/demo/.harness' };
const session = { id: 'conv_1', workspace_id: 'ws_1', title: '修复登录', created_at: '2026-01-01T00:00:00Z' };
const state = {
  runs: [] as unknown[],
  sessions: [] as unknown[],
  archived: [] as unknown[],
  createdSession: {} as Record<string, unknown>,
};

const calls: { path: string; init: RequestInit }[] = [];
let pinia: Pinia;
let wrapper: VueWrapper | undefined;

function completedRun(): unknown {
  return {
    id: 'run_live', status: 'success', input: '修复登录流程', totalTokens: 42, conversationId: session.id,
    nodes: [
      { id: 'step_1', kind: 'tool', name: 'workspace_read', status: 'success', input: { path: 'main.py' }, output: JSON.stringify({ status: 'success', data: { content: 'print(1)' } }) },
      { id: 'run_live-output', kind: 'output', name: '最终输出', status: 'success', output: '## 完成\n\n已修复登录流程。' },
    ],
  };
}

/** state.runs 里混入别的会话的 Run，用来验证客户端也会做会话隔离。 */
function respond(path: string, init: RequestInit): unknown {
  if (path === '/v1/workspaces') return init.method === 'POST' ? workspace : { items: [workspace] };
  if (path === '/v1/sessions' && init.method === 'POST') return state.createdSession;
  if (path.startsWith('/v1/sessions?') || path === '/v1/sessions') {
    const archived = path.includes('archived=true');
    return { items: archived ? state.archived : state.sessions };
  }
  if (path.startsWith('/v1/sessions/')) return init.method === 'DELETE' ? { removed: true, runs: 1 } : { ...session, archived: 1 };
  if (path.startsWith('/v1/runs?')) return { items: state.runs };
  if (path === '/v1/runs' && init.method === 'POST') return { run_id: 'run_live', conversation_id: session.id, status: 'pending' };
  if (path.startsWith('/v1/directories')) return { path: 'E:/project', parent: 'E:/', directories: [{ name: 'demo', path: 'E:/project/demo' }], roots: ['E:/'] };
  return { status: 'accepted' };
}

beforeEach(() => {
  localStorage.clear();
  calls.length = 0;
  state.runs = [];
  state.sessions = [session];
  state.archived = [];
  state.createdSession = { ...session, id: 'conv_2', title: '新任务' };
  FakeEventSource.instances = [];
  pinia = createPinia();
  setActivePinia(pinia);
  vi.stubGlobal('EventSource', FakeEventSource);
  vi.stubGlobal('fetch', vi.fn(async (path: string, init: RequestInit = {}) => {
    calls.push({ path, init });
    return new Response(JSON.stringify(respond(path, init)), { headers: { 'content-type': 'application/json' } });
  }));
});

afterEach(() => { wrapper?.unmount(); wrapper = undefined; disposePinia(pinia); vi.unstubAllGlobals(); });

const button = (text: string) => wrapper!.findAll('button').find(item => item.text().includes(text))!;
const stream = () => FakeEventSource.instances[FakeEventSource.instances.length - 1]!;

async function boot(): Promise<void> {
  wrapper = mount(App, { attachTo: document.body, global: { plugins: [pinia] } });
  await flushPromises();
}

async function ask(text: string): Promise<void> {
  await wrapper!.find('textarea').setValue(text);
  await wrapper!.find('form.composer').trigger('submit');
  await flushPromises();
}

describe('workspace lifecycle', () => {
  it('loads workspaces and sessions from the server on boot', async () => {
    await boot();
    expect(wrapper!.text()).toContain('demo');
    expect(wrapper!.text()).toContain('修复登录');
    expect(useChat().workspaceId).toBe('ws_1');
    expect(calls.some(call => call.path.startsWith('/v1/sessions?workspace_id=ws_1'))).toBe(true);
  });

  it('creates a workspace through the dialog', async () => {
    await boot();
    await button('＋').trigger('click');
    await flushPromises();
    expect(wrapper!.find('.creator').exists()).toBe(true);

    await wrapper!.find('.creator input[type="text"]').setValue('E:/project/new');
    await button('添加工作区').trigger('click');
    await flushPromises();

    const created = calls.find(call => call.path === '/v1/workspaces' && call.init.method === 'POST');
    expect(JSON.parse(String(created?.init.body))).toEqual({ path: 'E:/project/new', name: '', create: false });
  });

  it('never reports success when the backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    const chat = useChat();
    await chat.load();
    expect(chat.connected).toBe(false);
    expect(chat.error).toContain('无法连接');
    expect(chat.workspaces).toHaveLength(0);
  });
});

describe('streaming conversation', () => {
  it('streams model text as markdown and records tool calls', async () => {
    await boot();
    await ask('修复登录流程');

    const submitted = calls.find(call => call.path === '/v1/runs' && call.init.method === 'POST');
    expect(JSON.parse(String(submitted?.init.body))).toEqual({ input: '修复登录流程', workspace_id: 'ws_1', conversation_id: 'conv_1' });
    expect(stream().url).toBe('/v1/runs/run_live/stream');

    stream().emit({ type: 'model.start', step: 1 });
    stream().emit({ type: 'model.delta', text: '# 计划\n\n' });
    stream().emit({ type: 'model.delta', text: '先读取 `main.py`。' });
    await nextTick();
    expect(wrapper!.find('.markdown h1').text()).toBe('计划');
    expect(wrapper!.find('.markdown code').text()).toBe('main.py');

    stream().emit({
      type: 'model.end', step: 1, text: '# 计划\n\n先读取 `main.py`。',
      tool_calls: [{ call_id: 'call_1', name: 'workspace_read', arguments: { path: 'main.py' } }],
    });
    await nextTick();
    const card = wrapper!.find('[data-tool="workspace_read"]');
    expect(card.exists()).toBe(true);
    expect(card.attributes('class')).toContain('state-running');

    stream().emit({ type: 'tool.start', call_id: 'call_1', name: 'workspace_read', arguments: { path: 'main.py' } });
    stream().emit({
      type: 'tool.end', call_id: 'call_1', name: 'workspace_read', status: 'success',
      output: JSON.stringify({ status: 'success', data: { content: 'print(1)' } }),
    });
    await nextTick();
    expect(card.text()).toContain('完成');

    expect(card.find('button').attributes('aria-expanded')).toBe('false');
    expect(card.find('.tool-output').isVisible()).toBe(false);
    await card.find('button').trigger('click');
    expect(card.find('.tool-output').isVisible()).toBe(true);
    expect(wrapper!.find('.tool-output').text()).toContain('print(1)');
  });

  it('replaces the live transcript with the persisted run when the stream ends', async () => {
    await boot();
    await ask('修复登录流程');
    stream().emit({ type: 'model.start', step: 1 });
    stream().emit({ type: 'model.delta', text: '临时输出' });
    await nextTick();
    expect(wrapper!.text()).toContain('临时输出');

    state.runs = [completedRun()];
    stream().emit({ type: 'run.end', status: 'completed', output: '## 完成\n\n已修复登录流程。' });
    await flushPromises();

    expect(wrapper!.text()).not.toContain('临时输出');
    expect(wrapper!.find('.markdown h2').text()).toBe('完成');
    expect(wrapper!.find('[data-tool="workspace_read"]').exists()).toBe(true);
    expect(wrapper!.text()).toContain('已完成');
  });

  it('waits for approval and resumes the same run', async () => {
    await boot();
    await ask('写入文件');
    stream().emit({ type: 'model.start', step: 1 });
    stream().emit({
      type: 'model.end', step: 1, text: '',
      tool_calls: [{ call_id: 'call_9', name: 'workspace_write', arguments: { path: 'a.txt', content: 'x' } }],
    });
    stream().emit({ type: 'run.waiting', phase: 'waiting_approval', call_id: 'call_9', tool_name: 'workspace_write', arguments: { path: 'a.txt', content: 'x' } });
    await nextTick();
    expect(wrapper!.text()).toContain('需要你的批准');
    expect(wrapper!.find('[data-tool="workspace_write"]').attributes('class')).toContain('state-waiting');

    await wrapper!.find('.approval .primary').trigger('click');
    await flushPromises();
    expect(calls.some(call => call.path === '/v1/runs/run_live/approve' && call.init.method === 'POST')).toBe(true);
    expect(wrapper!.find('[data-tool="workspace_write"]').attributes('class')).toContain('state-running');
  });

  it('ignores replayed frames when the browser reconnects', async () => {
    await boot();
    await ask('输出一段文字');
    const source = stream();
    source.emit({ type: 'run.submitted', seq: 1 });
    source.emit({ type: 'model.start', step: 1, seq: 2 });
    source.emit({ type: 'model.delta', seq: 3, text: '第一段' });
    await nextTick();
    expect(wrapper!.find('.markdown').text()).toBe('第一段');

    // EventSource 自动重连时服务端会从缓冲开头整体重放，客户端必须保持幂等。
    source.emit({ type: 'run.submitted', seq: 1 });
    source.emit({ type: 'model.start', step: 1, seq: 2 });
    source.emit({ type: 'model.delta', seq: 3, text: '第一段' });
    await nextTick();
    expect(wrapper!.find('.markdown').text()).toBe('第一段');
    expect(wrapper!.findAll('.markdown')).toHaveLength(1);
  });

  it('maps a persisted run with tools into the same transcript shape', () => {
    const turn = turnFromRun(completedRun() as never);
    expect(turn.status).toBe('success');
    expect(turn.input).toBe('修复登录流程');
    expect(turn.blocks[0]).toMatchObject({ kind: 'tools' });
    expect(turn.blocks[1]).toMatchObject({ kind: 'text', text: '## 完成\n\n已修复登录流程。' });
  });

  it('renders tool bubbles from the server view when the event stream is dead', async () => {
    vi.useFakeTimers();
    try {
      await boot();
      await ask('读取项目');
      // 事件流一条都没到（旧服务 / 代理缓冲 / 断线）：看门狗必须补齐工具气泡。
      expect(wrapper!.findAll('[data-tool]')).toHaveLength(0);

      state.runs = [completedRun()];
      await vi.advanceTimersByTimeAsync(2100);
      await flushPromises();

      expect(wrapper!.find('[data-tool="workspace_read"]').exists()).toBe(true);
      expect(wrapper!.text()).toContain('完成');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('session management', () => {
  it('keeps a new session empty even if the server returns foreign runs', async () => {
    const chat = useChat();
    await boot();
    // 服务端（或旧版本服务）返回了属于别的会话的 Run。
    state.runs = [completedRun(), { ...(completedRun() as Record<string, unknown>), id: 'run_other', conversationId: 'conv_other' }];
    await chat.selectSession(session.id);
    expect(chat.turns.map(turn => turn.id)).toEqual(['run_live']);

    await chat.newSession();
    expect(chat.sessionId).toBe('conv_2');
    expect(chat.turns).toHaveLength(0);
  });

  it('titles a still-default session from the first instruction', async () => {
    await boot();
    await ask('把这段对话保存为 note');
    // 已有标题的会话不被覆盖。
    expect(calls.some(call => call.path === '/v1/sessions/conv_1' && call.init.method === 'PATCH')).toBe(false);

    await wrapper!.find('.side-section.grow header button').trigger('click');
    await flushPromises();
    expect(useChat().sessionId).toBe('conv_2');
    await ask('重构登录模块');
    const patch = calls.find(call => call.path === '/v1/sessions/conv_2' && call.init.method === 'PATCH');
    expect(JSON.parse(String(patch?.init.body))).toEqual({ title: '重构登录模块' });
  });

  it('archives and restores a session from the sidebar', async () => {
    await boot();
    await button('归档').trigger('click');
    await flushPromises();
    const patch = calls.find(call => call.path === '/v1/sessions/conv_1' && call.init.method === 'PATCH');
    expect(JSON.parse(String(patch?.init.body))).toEqual({ archived: true });
    expect(useChat().sessions).toHaveLength(0);
    expect(useChat().archivedSessions).toHaveLength(1);

    await button('已归档').trigger('click');
    await flushPromises();
    await button('恢复').trigger('click');
    await flushPromises();
    expect(useChat().archivedSessions).toHaveLength(0);
    expect(useChat().sessions).toHaveLength(1);
  });

  it('requires confirmation before deleting a session', async () => {
    await boot();
    await button('删除').trigger('click');
    await nextTick();
    expect(wrapper!.find('.confirm').text()).toContain('修复登录');
    expect(calls.some(call => call.init.method === 'DELETE')).toBe(false);

    await wrapper!.find('.confirm .danger-solid').trigger('click');
    await flushPromises();
    expect(calls.some(call => call.path === '/v1/sessions/conv_1' && call.init.method === 'DELETE')).toBe(true);
    expect(useChat().sessions).toHaveLength(0);
  });
});

describe('markdown rendering', () => {
  it('renders headings, code and lists', () => {
    wrapper = mount(MarkdownText, { props: { text: '# 标题\n\n- 一\n- 二\n\n```py\nprint(1)\n```' } });
    expect(wrapper.find('h1').text()).toBe('标题');
    expect(wrapper.findAll('li')).toHaveLength(2);
    expect(wrapper.find('pre code').text()).toContain('print(1)');
  });

  it('strips executable markup from model output', () => {
    wrapper = mount(MarkdownText, { props: { text: '<script>window.hacked = 1</script>\n\n<img src=x onerror="window.hacked = 2">' } });
    expect(wrapper.find('script').exists()).toBe(false);
    expect(wrapper.find('img').attributes('onerror')).toBeUndefined();
  });
});

describe('appearance and activity rows', () => {
  it('persists appearance choices and restores them on a fresh mount', async () => {
    await boot();
    expect(document.documentElement.dataset.font).toBe('serif');
    await wrapper!.find('[aria-label="外观设置"]').trigger('click');
    await wrapper!.find('input[name="theme"][value="paper"]').setValue();
    await wrapper!.find('input[name="font"][value="sans"]').setValue();
    expect(document.documentElement.dataset.theme).toBe('paper');
    expect(document.documentElement.dataset.font).toBe('sans');
    expect(JSON.parse(localStorage.getItem(APPEARANCE_KEY)!)).toEqual({ theme: 'paper', font: 'sans' });
    wrapper!.unmount();
    disposePinia(pinia);
    pinia = createPinia();
    setActivePinia(pinia);
    await boot();
    expect(document.documentElement.dataset.theme).toBe('paper');
    expect(document.documentElement.dataset.font).toBe('sans');
  });

  it('falls back to defaults for unsupported saved preferences', async () => {
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify({ theme: 'unknown', font: 'unknown' }));
    await boot();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.dataset.font).toBe('serif');
  });

  it('collapses each historical activity independently and keeps the final reply visible', async () => {
    state.runs = [{
      id: 'run_history', status: 'success', input: '检查代码', conversationId: session.id,
      nodes: [
        { id: 'thought', kind: 'thought', name: '模型', output: '先阅读项目结构。' },
        { id: 'read', kind: 'tool', name: 'workspace_read', status: 'success', input: { path: 'main.py' }, output: 'print(1)' },
        { id: 'result', kind: 'result', name: '检查', output: '检查已完成。' },
        { id: 'last-model', kind: 'thought', name: '模型', output: '最终答复。' },
        { id: 'output', kind: 'output', name: '输出', output: '最终答复。' },
      ],
    }];
    await boot();
    const rows = wrapper!.findAll('.activity-row');
    expect(rows).toHaveLength(3);
    expect(rows.map(row => row.find('.activity-label').text())).toEqual(['思考', '读取', '执行步骤']);
    for (const row of rows) expect(row.find('.activity-body').isVisible()).toBe(false);
    expect(wrapper!.find('.turn > .markdown').isVisible()).toBe(true);
    expect(wrapper!.find('.turn > .markdown').text()).toBe('最终答复。');
    await rows[0]!.find('button').trigger('click');
    expect(rows[0]!.find('.activity-body').isVisible()).toBe(true);
    expect(rows[1]!.find('.activity-body').isVisible()).toBe(false);
    await rows[0]!.find('button').trigger('click');
    expect(rows[0]!.find('.activity-body').isVisible()).toBe(false);
  });

  it('keeps streamed process text collapsed then displays the final model response', async () => {
    await boot();
    await ask('检查代码');
    stream().emit({ type: 'model.start', step: 1 });
    stream().emit({ type: 'model.delta', text: '先读代码。' });
    await nextTick();
    expect(wrapper!.find('.activity-body').isVisible()).toBe(false);
    stream().emit({ type: 'model.end', text: '先读代码。', tool_calls: [{ call_id: 'read', name: 'workspace_read', arguments: { path: 'main.py' } }] });
    stream().emit({ type: 'model.start', step: 2 });
    stream().emit({ type: 'model.delta', text: '完成。' });
    stream().emit({ type: 'model.end', text: '完成。', tool_calls: [] });
    await nextTick();
    expect(wrapper!.findAll('.activity-toggle').map(row => row.attributes('aria-expanded'))).toEqual(['false', 'false']);
    expect(wrapper!.find('.turn > .markdown').text()).toBe('完成。');
  });
});
