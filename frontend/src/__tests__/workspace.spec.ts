import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { nextTick } from 'vue';
import App from '@/App.vue';
import MarkdownText from '@/components/MarkdownText.vue';
import { useChat, turnFromRun } from '@/stores/chat';
import { APPEARANCE_KEY, useAppearance } from '@/stores/appearance';
import { LAYOUT_KEY } from '@/composables/usePanelLayout';
import CapabilityPage from '@/components/CapabilityPage.vue';
import PersonalPage from '@/components/PersonalPage.vue';
import ConversationMetrics from '@/components/ConversationMetrics.vue';
import ConversationLocator from '@/components/ConversationLocator.vue';
import type { Turn } from '@/stores/chat';

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
  workspaces: [workspace],
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
  if (path === '/v1/skills' || path === '/v1/automations') return { items: [] };
  if (path === '/v1/preferences') return { content: '' };
  if (path === '/v1/workspaces') return init.method === 'POST' ? workspace : { items: state.workspaces };
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
  window.history.replaceState(null, '', '/#/chat?workspace=ws_1');
  localStorage.clear();
  state.workspaces = [workspace];
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

describe('personal workspace features', () => {
  it('creates ordinary conversations from the top navigation without requiring a workspace', async () => {
    window.history.replaceState(null, '', '/');
    state.workspaces = []; state.sessions = [];
    state.createdSession = { ...session, id: 'normal', workspace_id: '', title: '新任务' };
    await boot();
    expect(wrapper!.find('textarea').attributes('disabled')).toBeUndefined();
    const sections = wrapper!.findAll('.sidebar-content > section');
    expect(sections.map(item => item.attributes('aria-label'))).toEqual(['项目', '普通对话']);
    await button('新对话').trigger('click');
    await flushPromises();
    expect(useChat().workspaceId).toBe('');
    expect(window.location.hash).toBe('#/chat?session=normal');
    expect(wrapper!.find('.creator').exists()).toBe(false);
    await ask('普通消息');
    const post = calls.find(item => item.path === '/v1/runs' && item.init.method === 'POST')!;
    expect(JSON.parse(String(post.init.body))).toEqual({ input: '普通消息', conversation_id: 'normal' });
  });

  it('streams a temporary reply and clears it on pagehide without durable requests', async () => {
    window.history.replaceState(null, '', '/');
    const normalFetch = fetch;
    vi.stubGlobal('fetch', vi.fn(async (path: string, init: RequestInit = {}) => {
      if (!path.startsWith('/v1/temporary-chats')) return normalFetch(path, init);
      calls.push({ path, init });
      if (path.endsWith('/messages')) return new Response('data: {"type":"model.delta","text":"临时回复"}\n\ndata: {"type":"run.end","output":"临时回复"}\n\n', { headers: { 'Content-Type': 'text/event-stream' } });
      return new Response(JSON.stringify({ id: 'temp_1' }), { headers: { 'Content-Type': 'application/json' } });
    }));
    await boot();
    await wrapper!.find('button[aria-label="临时对话"]').trigger('click');
    await flushPromises();
    expect(wrapper!.find('.temporary-chat').exists()).toBe(true);
    await ask('临时秘密');
    expect(wrapper!.find('.transcript').text()).toContain('临时回复');
    expect(calls.some(item => item.path === '/v1/runs' && item.init.method === 'POST')).toBe(false);
    expect(JSON.stringify(localStorage)).not.toContain('临时秘密');
    window.dispatchEvent(new Event('pagehide'));
    expect(useChat().turns).toHaveLength(0);
    expect(calls.some(item => item.path === '/v1/temporary-chats/temp_1/end' && item.init.keepalive)).toBe(true);
  });

  it('imports SKILL.md and sends selected skill IDs with ordinary chat', async () => {
    wrapper = mount(PersonalPage, { props: { page: 'skills' }, global: { plugins: [pinia] } });
    await flushPromises();
    const input = wrapper.find('input[type="file"]');
    Object.defineProperty(input.element, 'files', { value: [{ size: 80, text: async () => '---\nname: concise\ndescription: 简洁\n---\n短句回答' }] });
    await input.trigger('change'); await flushPromises();
    expect(calls.find(item => item.path === '/v1/skills/import')?.init.body).toContain('name: concise');
    wrapper.unmount(); wrapper = undefined;
    const chat = useChat();
    await chat.selectWorkspace('');
    state.createdSession = { ...session, workspace_id: '', id: 'normal' };
    chat.selectedSkills = ['skill_1'];
    await chat.send('你好');
    expect(JSON.parse(String(calls.find(item => item.path === '/v1/runs' && item.init.method === 'POST')?.init.body)).skill_ids).toEqual(['skill_1']);
    await chat.selectWorkspace('');
  });

  it('creates a scheduled task from the form with an explicit timezone', async () => {
    wrapper = mount(PersonalPage, { props: { page: 'automations' }, global: { plugins: [pinia] } });
    await flushPromises();
    await button('创建定时任务').trigger('click');
    await wrapper.find('input[maxlength="120"]').setValue('每小时总结');
    await wrapper.find('textarea').setValue('总结目标');
    await wrapper.find('input[type="datetime-local"]').setValue('2099-01-02T10:00');
    await wrapper.find('select').setValue('3600');
    await wrapper.find('form').trigger('submit'); await flushPromises();
    const body = JSON.parse(String(calls.find(item => item.path === '/v1/automations' && item.init.method === 'POST')?.init.body));
    expect(body).toMatchObject({ name: '每小时总结', interval_seconds: 3600, workspace_id: null });
    expect(body.run_at).toMatch(/Z$/);
  });

  it('creates a RAG repository and uploads into that repository', async () => {
    vi.stubGlobal('fetch', vi.fn(async (path: string, init: RequestInit = {}) => {
      calls.push({ path, init });
      const repo = { id: 'kb_new', name: '新知识库', description: '', embedding_model: 'qwen' };
      const body = init.method === 'POST' ? repo : { items: path.endsWith('/files') ? [] : [repo] };
      return new Response(JSON.stringify(body), { headers: { 'Content-Type': 'application/json' } });
    }));
    wrapper = mount(CapabilityPage, { props: { page: 'explore' } });
    await flushPromises();
    await button('创建知识库').trigger('click');
    await wrapper.find('input[maxlength="120"]').setValue('新知识库');
    await wrapper.find('form').trigger('submit'); await flushPromises();
    expect(calls.find(item => item.path === '/v1/knowledge/repositories' && item.init.method === 'POST')?.init.body).toContain('新知识库');
    const input = wrapper.find('input[type="file"]');
    Object.defineProperty(input.element, 'files', { value: [new File(['知识'], 'guide.md', { type: 'text/markdown' })] });
    await input.trigger('change'); await flushPromises();
    expect(calls.some(item => item.path === '/v1/knowledge/repositories/kb_new/files?filename=guide.md' && item.init.method === 'POST')).toBe(true);
  });
});

async function boot(): Promise<void> {
  wrapper = mount(App, { attachTo: document.body, global: { plugins: [pinia] } });
  await flushPromises();
}

async function ask(text: string): Promise<void> {
  await wrapper!.find('textarea').setValue(text);
  await wrapper!.find('form.composer').trigger('submit');
  await flushPromises();
}

describe('project navigation', () => {
  const second = { ...workspace, id: 'ws_2', name: '另一个项目' };
  const secondSession = { ...session, id: 'conv_other', workspace_id: 'ws_2', title: '第二个项目的聊天' };
  function twoProjects(): void {
    state.workspaces = [workspace, second];
    // Deliberately mixed API data: each folder must retain only its own sessions.
    state.sessions = [session, secondSession];
  }

  it('groups conversations by project and switches with a shareable address', async () => {
    twoProjects();
    await boot();
    await wrapper!.find('[aria-label="展开项目 另一个项目"]').trigger('click');
    await flushPromises();
    const first = wrapper!.find('[data-workspace="ws_1"]');
    const other = wrapper!.find('[data-workspace="ws_2"]');
    expect(first.text()).toContain(session.title);
    expect(first.text()).not.toContain(secondSession.title);
    expect(other.text()).not.toContain(session.title);
    await other.find('.session-open').trigger('click');
    await flushPromises();
    expect(useChat().workspaceId).toBe('ws_2');
    expect(useChat().sessionId).toBe(secondSession.id);
    expect(window.location.hash).toBe('#/chat?workspace=ws_2&session=conv_other');
    expect(first.find('.session-open').exists()).toBe(true);
  });

  it('opens a direct chat address and rejects a session from another workspace', async () => {
    twoProjects();
    window.history.replaceState(null, '', '#/chat?workspace=ws_2&session=conv_other');
    await boot();
    expect(useChat().sessionId).toBe(secondSession.id);
    window.history.pushState(null, '', '#/chat?workspace=ws_1&session=conv_other');
    window.dispatchEvent(new PopStateEvent('popstate'));
    await flushPromises();
    expect(wrapper!.find('.route-page').text()).toContain('不属于当前工作区');
    expect(wrapper!.find('.conversation-view').isVisible()).toBe(false);
  });

  it('archives a chat in an inactive project without changing the current conversation', async () => {
    twoProjects();
    await boot();
    await wrapper!.find('[aria-label="展开项目 另一个项目"]').trigger('click');
    await flushPromises();
    await wrapper!.find('[data-workspace="ws_2"] [title="归档会话"]').trigger('click');
    await flushPromises();
    expect(useChat().sessionId).toBe(session.id);
    expect(useChat().sessionGroups.ws_1?.active).toHaveLength(1);
    expect(useChat().sessionGroups.ws_2?.active).toHaveLength(0);
    expect(useChat().sessionGroups.ws_2?.archived[0]?.id).toBe(secondSession.id);
  });

  it('keeps the draft and live stream while visiting pages and restores via browser history', async () => {
    await boot();
    await wrapper!.find('textarea').setValue('保留这份草稿');
    const href = window.location.hash;
    await wrapper!.find('a[href="#/pull-requests"]').trigger('click');
    await flushPromises();
    expect(wrapper!.find('.route-page').text()).toContain('尚未提供 Pull Request');
    expect(calls.some(call => call.path.includes('pull-request'))).toBe(false);
    window.history.back();
    await vi.waitFor(() => expect(window.location.hash).toBe(href));
    await flushPromises();
    expect(wrapper!.find('textarea').element.value).toBe('保留这份草稿');
    await ask('读取项目');
    const source = stream();
    await wrapper!.find('a[href="#/automations"]').trigger('click');
    await flushPromises();
    expect(wrapper!.find('.route-page').text()).toContain('创建定时任务');
    expect(source.readyState).toBe(FakeEventSource.OPEN);
    source.emit({ type: 'model.start', step: 1 });
    source.emit({ type: 'model.delta', text: '继续接收的内容' });
    await nextTick();
    await wrapper!.find('[data-workspace="ws_1"] .session-open').trigger('click');
    await flushPromises();
    expect(wrapper!.find('.transcript').text()).toContain('继续接收的内容');
  });

  it('handles unknown page addresses without creating a conversation', async () => {
    window.history.replaceState(null, '', '#/missing');
    await boot();
    expect(wrapper!.find('.route-page').text()).toContain('页面不存在');
    expect(calls.some(call => call.init.method === 'POST')).toBe(false);
  });
});

describe('capability pages', () => {
  it('reads MCP tools and knowledge files from the supported endpoints', async () => {
    const fetched: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
      fetched.push(path);
      const items = path === '/v1/mcp/servers' ? [{ name: 'local-tools', transport: 'stdio', tools: ['repo_read'] }]
        : path.endsWith('/files') ? [{ id: 'f1', filename: 'guide.md', chunk_count: 3, size_bytes: 120 }]
          : [{ id: 'kb1', name: '项目文档', description: '开发资料', embedding_model: 'local-model' }];
      return new Response(JSON.stringify({ items }), { headers: { 'content-type': 'application/json' } });
    }));
    wrapper = mount(CapabilityPage, { props: { page: 'plugins' } });
    await flushPromises();
    expect(wrapper.text()).toContain('repo_read');
    await wrapper.setProps({ page: 'explore' });
    await flushPromises();
    await wrapper.find('.repository-toggle').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('guide.md');
    expect(fetched).toEqual(['/v1/mcp/servers', '/v1/knowledge/repositories', '/v1/knowledge/repositories/kb1/files']);
  });

  it('shows disabled service errors and allows retry into an honest empty state', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'MCP 未启用' }), { status: 503, headers: { 'content-type': 'application/json' } })));
    wrapper = mount(CapabilityPage, { props: { page: 'plugins' } });
    await flushPromises();
    expect(wrapper.text()).toContain('MCP 未启用');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ items: [] }), { headers: { 'content-type': 'application/json' } })));
    await button('重试').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('还没有连接的 MCP 服务');
    expect(wrapper.text()).not.toContain('MCP 未启用');
  });
});

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
    await wrapper!.find('a[href="#/pull-requests"]').trigger('click');
    await wrapper!.find('[aria-label="新建工作区"]').trigger('click');
    await flushPromises();
    expect(wrapper!.find('.creator').exists()).toBe(true);

    await wrapper!.find('.creator input[type="text"]').setValue('E:/project/new');
    await button('添加工作区').trigger('click');
    await flushPromises();

    const created = calls.find(call => call.path === '/v1/workspaces' && call.init.method === 'POST');
    expect(JSON.parse(String(created?.init.body))).toEqual({ path: 'E:/project/new', name: '', create: false });
    expect(window.location.hash).toBe('#/chat?workspace=ws_1&session=conv_1');
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
  it('sends through the composer action and replaces it with a working stop control', async () => {
    await boot();
    expect(wrapper!.find('.composer-send').attributes('disabled')).toBeDefined();
    await wrapper!.find('textarea').setValue('检查项目结构');
    await wrapper!.find('.composer-send').trigger('click');
    await flushPromises();
    expect(calls.some(call => call.path === '/v1/runs' && call.init.method === 'POST')).toBe(true);
    expect(wrapper!.find('.composer-send').attributes('aria-label')).toBe('停止运行');
    await wrapper!.find('.composer-send').trigger('click');
    await flushPromises();
    expect(calls.some(call => call.path === '/v1/runs/run_live/cancel' && call.init.method === 'POST')).toBe(true);
  });

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

    await wrapper!.find('[aria-label="在 demo 新建会话"]').trigger('click');
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
  it('previews and jumps between conversation turns and tracks manual scrolling', async () => {
    const scroller = document.createElement('div');
    document.body.append(scroller);
    Object.defineProperties(scroller, { scrollHeight: { value: 1500 }, clientHeight: { value: 300 } });
    scroller.getBoundingClientRect = () => ({ top: 100 } as DOMRect);
    const turns: Turn[] = [0, 1, 2].map(index => ({ id: `jump_${index}`, input: `第 ${index + 1} 个问题`, status: 'success', blocks: [{ kind: 'text', text: `第 ${index + 1} 个答复`, streaming: false }], error: '', tokens: 0, seq: 0 }));
    turns.forEach((turn, index) => {
      const article = document.createElement('article'); article.className = 'turn'; article.dataset.run = turn.id;
      article.getBoundingClientRect = () => ({ top: 100 + index * 400 - scroller.scrollTop } as DOMRect);
      scroller.append(article);
    });
    scroller.scrollTo = vi.fn((options: ScrollToOptions) => { scroller.scrollTop = options.top ?? 0; scroller.dispatchEvent(new Event('scroll')); }) as typeof scroller.scrollTo;
    wrapper = mount(ConversationLocator, { attachTo: document.body, props: { turns, scroller } });
    try {
      await vi.waitFor(() => expect(wrapper!.findAll('button')[0]!.attributes('aria-current')).toBe('location'));
      await wrapper.findAll('button')[1]!.trigger('mouseenter');
      expect(wrapper.find('[role="tooltip"]').text()).toContain('第 2 个问题');
      expect(wrapper.find('[role="tooltip"]').text()).toContain('第 2 个答复');
      await wrapper.findAll('button')[1]!.trigger('click');
      expect(scroller.scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 368 }));
      expect(wrapper.emitted('navigate')).toHaveLength(1);
      scroller.scrollTop = 1200; scroller.dispatchEvent(new Event('scroll'));
      await vi.waitFor(() => expect(wrapper!.findAll('button')[2]!.attributes('aria-current')).toBe('location'));
      await wrapper.setProps({ turns: [] });
      expect(wrapper.find('[aria-label="对话快速定位"]').exists()).toBe(false);
      expect(wrapper.find('[role="tooltip"]').exists()).toBe(false);
    } finally { scroller.remove(); }
  });
  it('edits habits inside the settings modal while preserving the chat draft', async () => {
    await boot();
    await wrapper!.find('textarea[aria-label="消息"]').setValue('未发送草稿');
    expect(wrapper!.find('.workspace-nav a[href="#/preferences"]').exists()).toBe(false);
    await wrapper!.find('[aria-label="设置"]').trigger('click');
    await button('使用习惯').trigger('click');
    await flushPromises();
    const habits = wrapper!.find('.settings-preferences textarea');
    await habits.setValue('先给结论，默认中文');
    await wrapper!.find('.settings-preferences form').trigger('submit');
    await flushPromises();
    expect(calls.find(item => item.path === '/v1/preferences' && item.init.method === 'PUT')?.init.body).toContain('先给结论，默认中文');
    await wrapper!.find('[aria-label="关闭设置"]').trigger('click');
    expect(wrapper!.find<HTMLTextAreaElement>('textarea[aria-label="消息"]').element.value).toBe('未发送草稿');
  });

  it('persists custom colors, rejects invalid HEX, and resets only color overrides', async () => {
    await boot();
    await wrapper!.find('[aria-label="设置"]').trigger('click');
    await button('自定义配色').trigger('click');
    await wrapper!.find('[aria-label="使用强调色 #7ca7e8"]').trigger('click');
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe('#7ca7e8');
    expect(document.documentElement.style.getPropertyValue('--send-bg')).toBe('#7ca7e8');
    const hex = wrapper!.find('[aria-label="强调色 HEX"]');
    await hex.setValue('invalid');
    expect(useAppearance().accent).toBe('#7ca7e8');
    await hex.setValue('#113355');
    expect(document.documentElement.style.getPropertyValue('--primary-text')).toBe('#ffffff');
    const appearance = useAppearance();
    appearance.customColors = true; appearance.palette.background = '#f7f1e3'; appearance.palette.surface = '#fffaf0'; appearance.palette.text = '#333333'; appearance.font = 'sans';
    await nextTick();
    const saved = JSON.parse(localStorage.getItem(APPEARANCE_KEY)!);
    expect(saved).toMatchObject({ customAccent: true, accent: '#113355', customColors: true, palette: { background: '#f7f1e3' } });
    wrapper!.unmount(); disposePinia(pinia); pinia = createPinia(); setActivePinia(pinia);
    await boot();
    expect(document.documentElement.style.getPropertyValue('--bg')).toBe('#f7f1e3');
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe('#113355');
    useAppearance().resetColors();
    expect(document.documentElement.style.getPropertyValue('--bg')).toBe('');
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe('');
    expect(useAppearance().font).toBe('sans');
  });

  it('opens legacy preferences links in settings and validates stored colors', async () => {
    window.history.replaceState(null, '', '#/preferences');
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify({ customColors: true, customAccent: true, accent: 'url(bad)', palette: { background: 'red; display:none', text: '#123456' } }));
    await boot();
    expect(wrapper!.find('dialog').element.open).toBe(true);
    expect(wrapper!.find('.settings-preferences').isVisible()).toBe(true);
    expect(window.location.hash).toContain('#/chat');
    expect(useAppearance().accent).toBe('#d6ad60');
    expect(useAppearance().palette.background).toBe('#131413');
    expect(useAppearance().palette.text).toBe('#123456');
  });

  it('persists appearance choices and restores them on a fresh mount', async () => {
    await boot();
    expect(document.documentElement.dataset.font).toBe('serif');
    await wrapper!.find('[aria-label="设置"]').trigger('click');
    await wrapper!.find('input[name="theme"][value="paper"]').setValue();
    await wrapper!.find('input[name="font"][value="sans"]').setValue();
    expect(document.documentElement.dataset.theme).toBe('paper');
    expect(document.documentElement.dataset.font).toBe('sans');
    expect(JSON.parse(localStorage.getItem(APPEARANCE_KEY)!)).toMatchObject({ theme: 'paper', font: 'sans' });
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

describe('resizable layout', () => {
  async function pointer(element: Element, type: string, options: PointerEventInit): Promise<void> {
    element.dispatchEvent(new PointerEvent(type, { bubbles: true, isPrimary: true, ...options }));
    await nextTick();
  }

  it('drags panels in both directions, clamps sizes and saves the result on release', async () => {
    await boot();
    const sidebar = wrapper!.find('[aria-label="调整侧栏宽度"]');
    await pointer(sidebar.element, 'pointerdown', { button: 0, pointerId: 1, clientX: 264 });
    await pointer(sidebar.element, 'pointermove', { pointerId: 1, clientX: 364 });
    expect(sidebar.attributes('aria-valuenow')).toBe('364');
    await pointer(sidebar.element, 'pointerup', { pointerId: 1, clientX: 364 });
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!).sidebarWidth).toBe(364);
    expect(sidebar.classes()).not.toContain('dragging');

    const composer = wrapper!.find('[aria-label="调整输入区高度"]');
    const initial = Number(composer.attributes('aria-valuenow'));
    await pointer(composer.element, 'pointerdown', { button: 0, pointerId: 2, clientY: 600 });
    await pointer(composer.element, 'pointermove', { pointerId: 2, clientY: 550 });
    expect(Number(composer.attributes('aria-valuenow'))).toBe(initial + 50);
    await pointer(composer.element, 'pointerup', { pointerId: 2, clientY: -5000 });
    expect(composer.attributes('aria-valuenow')).toBe(composer.attributes('aria-valuemax'));
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!).composerHeight).toBe(Number(composer.attributes('aria-valuemax')));
  });

  it('restores saved dimensions and supports keyboard adjustment, cancellation and reset', async () => {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebarWidth: 340, composerHeight: 210 }));
    await boot();
    const sidebar = wrapper!.find('[aria-label="调整侧栏宽度"]');
    expect(sidebar.attributes('aria-valuenow')).toBe('340');
    await sidebar.trigger('keydown', { key: 'ArrowRight' });
    expect(sidebar.attributes('aria-valuenow')).toBe('350');
    await pointer(sidebar.element, 'pointerdown', { button: 0, pointerId: 3, clientX: 350 });
    await pointer(sidebar.element, 'pointermove', { pointerId: 3, clientX: 450 });
    expect(sidebar.attributes('aria-valuenow')).toBe('450');
    await sidebar.trigger('keydown', { key: 'Escape' });
    expect(sidebar.attributes('aria-valuenow')).toBe('350');
    expect(sidebar.classes()).not.toContain('dragging');
    await sidebar.trigger('dblclick');
    expect(sidebar.attributes('aria-valuenow')).toBe('264');
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!).sidebarWidth).toBe(264);
    const composer = wrapper!.find('[aria-label="调整输入区高度"]');
    expect(composer.attributes('aria-valuenow')).toBe('210');
    await composer.trigger('keydown', { key: 'ArrowUp' });
    expect(composer.attributes('aria-valuenow')).toBe('220');
    await composer.trigger('keydown', { key: 'Enter' });
    expect(composer.attributes('aria-valuenow')).toBe('164');
  });

  it('keeps narrow-screen heights independent and recovers desktop width after resizing the window', async () => {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify({ sidebarWidth: 500, sidebarHeight: 160, composerHeight: 'bad' }));
    await boot();
    const desktopWidth = wrapper!.find('[aria-label="调整侧栏宽度"]').attributes('aria-valuenow');
    vi.stubGlobal('innerWidth', 600);
    window.dispatchEvent(new Event('resize'));
    await nextTick();
    const sidebar = wrapper!.find('[aria-label="调整侧栏高度"]');
    expect(sidebar.attributes('aria-orientation')).toBe('horizontal');
    expect(sidebar.attributes('aria-valuenow')).toBe('160');
    await sidebar.trigger('keydown', { key: 'ArrowDown' });
    expect(sidebar.attributes('aria-valuenow')).toBe('170');
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY)!).sidebarWidth).toBe(500);
    vi.stubGlobal('innerWidth', 1024);
    window.dispatchEvent(new Event('resize'));
    await nextTick();
    expect(wrapper!.find('[aria-label="调整侧栏宽度"]').attributes('aria-valuenow')).toBe(desktopWidth);
  });
});


describe('conversation metrics', () => {
  const metrics = { input_tokens: 1000, output_tokens: 200, total_tokens: 1200,
    cached_input_tokens: 800, duration_ms: 2000, context_window: 32000 };
  it('preserves server metrics through history and marks unavailable old data', async () => {
    const turn = turnFromRun({ id: 'r', status: 'success', input: 'hello', totalTokens: 1200,
      nodes: [{ id: 'm', kind: 'thought', name: 'model', metrics }] });
    wrapper = mount(ConversationMetrics, { props: { turns: [turn] }, global: { plugins: [pinia] } });
    expect(wrapper.text()).toContain('缓存命中 80%');
    expect(wrapper.text()).toContain('100.0 tok/s');
    expect(wrapper.text()).toContain('已用 1.2k tok');
    expect(wrapper.text()).toContain('上下文余量 ≈30.8k tok');
    await wrapper.setProps({ turns: [{ ...turn, metrics: { '1': { ...metrics, cached_input_tokens: null } } }] });
    expect(wrapper.text()).toContain('缓存命中 —');
    await wrapper.setProps({ turns: [{ ...turn, metrics: undefined }] });
    expect(wrapper.text()).toContain('上下文余量 —');
    expect(wrapper.text()).not.toContain('NaN');
    await wrapper.setProps({ turns: [] });
    expect(wrapper.text()).toContain('已用 —');
  });
  it('merges streamed metrics without counting replay twice and keeps visibility preferences', async () => {
    await boot(); await ask('metrics');
    const event = { type: 'model.end', seq: 1, step: 1, text: 'done', tokens: 1200, metrics };
    stream().emit(event); stream().emit(event); await nextTick();
    expect(useChat().turns.at(-1)?.tokens).toBe(1200);
    expect(wrapper!.find('.conversation-metrics').text()).toContain('缓存命中 80%');
    await wrapper!.find('[aria-label="设置"]').trigger('click');
    await button('对话指标').trigger('click');
    const inputs = wrapper!.findAll('.metric-options input');
    for (const input of inputs) await input.setValue(false);
    expect(wrapper!.find('.conversation-metrics').exists()).toBe(false);
    expect(JSON.parse(localStorage.getItem(APPEARANCE_KEY)!).metrics).toEqual({ cache: false, speed: false, tokens: false, context: false, steps: false });
    stream().emit({ ...event, seq: 2, step: 2, metrics: { ...metrics, cached_input_tokens: 0 } });
    await inputs[0]!.setValue(true);
    expect(wrapper!.find('.conversation-metrics').text()).toContain('缓存命中 40%');
  });
});
