import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { ApiError, request, streamRun, type RunEvent } from '@/api/client';
import { STORAGE_KEYS, readJSON, writeJSON } from '@/api/storage';

export interface Workspace { id: string; name: string; path: string; knowledge_path: string }
export interface Session { id: string; workspace_id: string; title: string; created_at: string; archived?: number }
export interface SessionGroup { active: Session[]; archived: Session[] }
export interface DirectoryListing { path: string; parent: string; directories: { name: string; path: string }[]; roots: string[] }

/** 与后端 observed_run 的 status 词表一一对应。 */
export type RunStatus = 'running' | 'waiting' | 'paused' | 'success' | 'failed' | 'cancelled';
export type ToolState = 'running' | 'waiting' | 'success' | 'failed' | 'skipped';

export interface FileDiff { path: string; before: string; after: string }
export interface ToolCallView {
  call_id: string;
  name: string;
  arguments: Record<string, unknown>;
  state: ToolState;
  status: string;
  output: string;
  diff: FileDiff | null;
}
export interface TextBlock { kind: 'text'; text: string; streaming: boolean; activity?: 'thought' | 'step' }
export interface ToolBlock { kind: 'tools'; calls: ToolCallView[] }
export type Block = TextBlock | ToolBlock;
export interface ModelMetrics {
  input_tokens: number; output_tokens: number; total_tokens: number;
  cached_input_tokens: number | null; duration_ms: number; context_window: number | null;
}
export function readMetrics(raw: unknown): ModelMetrics | undefined {
  if (!raw || typeof raw !== 'object') return;
  const m = raw as Record<string, unknown>;
  const valid = (n: unknown): n is number => typeof n === 'number' && Number.isFinite(n) && n >= 0;
  if (![m.input_tokens, m.output_tokens, m.total_tokens, m.duration_ms].every(valid)) return;
  return { input_tokens: m.input_tokens as number, output_tokens: m.output_tokens as number,
    total_tokens: m.total_tokens as number, duration_ms: m.duration_ms as number,
    cached_input_tokens: valid(m.cached_input_tokens) && m.cached_input_tokens <= (m.input_tokens as number) ? m.cached_input_tokens : null,
    context_window: valid(m.context_window) && m.context_window > 0 ? m.context_window : null };
}
export interface Turn {
  id: string;
  input: string;
  status: RunStatus;
  blocks: Block[];
  error: string;
  tokens: number;
  metrics?: Record<string, ModelMetrics>;
  /** 已归并的最后一条事件序号。浏览器重连会重放缓冲，靠它保持幂等。 */
  seq: number;
}

interface ObservedNode {
  id: string; kind: string; name: string; status?: string; tokens?: number;
  metrics?: unknown; input?: unknown; output?: unknown; diff?: FileDiff | null; error?: { message?: string };
}
interface ObservedRun { id: string; status: string; input: string; nodes: ObservedNode[]; totalTokens?: number; conversationId?: string | null }
interface Submission { run_id: string; conversation_id: string; blocked?: boolean; output?: string | null }

/**
 * 会话隔离：服务端已按 conversation_id 过滤，这里再按 Run 自带的会话字段核验一次。
 * 这样即使对面是没有过滤参数的旧服务，新会话也不会显示别的会话内容。
 */
export function selectSessionRuns(items: ObservedRun[], sessionId: string): ObservedRun[] {
  return items.filter(item => !item.conversationId || item.conversationId === sessionId);
}

export const STATUS_LABELS: Record<RunStatus, string> = {
  running: '执行中', waiting: '等待批准', paused: '已暂停', success: '已完成', failed: '失败', cancelled: '已取消',
};
export const TOOL_LABELS: Record<ToolState, string> = {
  running: '执行中', waiting: '等待批准', success: '完成', failed: '失败', skipped: '已跳过',
};

export const DEFAULT_SESSION_TITLE = '新任务';
/** 后端 observed_run 的终态：出现这些状态就说明不会再产生新事件。 */
const ACTIVE_RUN_STATUSES = new Set(['running', 'pending', 'paused', 'waiting']);

/** 用第一条指令生成会话标题，避免侧栏堆满同名条目。 */
export function titleFrom(input: string): string {
  const line = input.trim().split('\n')[0]?.trim() ?? '';
  return line.length > 24 ? `${line.slice(0, 24)}…` : line || DEFAULT_SESSION_TITLE;
}

/** 工具结果是 ToolResult 的 JSON 投影；这里同时兼容对象与字符串两种历史形态。 */
export function parseToolResult(raw: unknown): { text: string; diff: FileDiff | null; callId: string; resultStatus: string } {
  const empty = { text: '', diff: null, callId: '', resultStatus: '' };
  let payload: unknown = raw;
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return { ...empty, text: raw };
    try { payload = JSON.parse(trimmed); } catch { return { ...empty, text: raw } }
  }
  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    const callId = typeof record.call_id === 'string' ? record.call_id : '';
    const resultStatus = typeof record.status === 'string' ? record.status : '';
    const data = 'data' in record ? record.data : record;
    if (data && typeof data === 'object') {
      const inner = data as Record<string, unknown>;
      if (inner.diff && typeof inner.diff === 'object') return { text: '', diff: inner.diff as FileDiff, callId, resultStatus };
      if (typeof inner.stdout === 'string' || typeof inner.stderr === 'string') {
        return { text: [inner.stdout, inner.stderr].filter(part => typeof part === 'string' && part).join('\n'), diff: null, callId, resultStatus };
      }
      if (typeof inner.content === 'string') return { text: inner.content, diff: null, callId, resultStatus };
      if (Array.isArray(inner.entries)) {
        return { text: inner.entries.map(entry => (entry as { name?: string }).name ?? '').filter(Boolean).join('\n'), diff: null, callId, resultStatus };
      }
      return { text: JSON.stringify(inner, null, 2), diff: null, callId, resultStatus };
    }
    if (typeof data === 'string') return { text: data, diff: null, callId, resultStatus };
    if (data === null || data === undefined) return { text: resultStatus, diff: null, callId, resultStatus };
  }
  return { ...empty, text: String(payload ?? '') };
}

function toolState(status: string): ToolState {
  if (status === 'success') return 'success';
  if (status === 'pending' || status === 'approval_required' || status === 'reconciliation_required') return 'waiting';
  if (status === 'skipped') return 'skipped';
  if (!status || status === 'running') return 'running';
  return 'failed';
}

function statusFromApi(status: string): RunStatus {
  if (status === 'success' || status === 'completed') return 'success';
  if (status === 'failed' || status === 'blocked') return 'failed';
  if (status === 'skipped' || status === 'cancelled') return 'cancelled';
  if (status === 'paused') return 'paused';
  if (status === 'pending' || status === 'waiting') return 'waiting';
  return 'running';
}

function callFromNode(node: ObservedNode): ToolCallView {
  const parsed = parseToolResult(node.output);
  return {
    // 同一 call_id 的等待步骤与执行步骤会合并成一张卡片，以 call_id 作为身份。
    call_id: parsed.callId || node.id,
    name: node.name,
    arguments: (node.input && typeof node.input === 'object' ? node.input : {}) as Record<string, unknown>,
    state: toolState(node.status ?? parsed.resultStatus ?? 'success'),
    status: node.status ?? parsed.resultStatus ?? 'success',
    output: parsed.text,
    diff: node.diff ?? parsed.diff,
  };
}

/** 把一条持久化 Run 投影成与实时流完全一致的对话轮次。 */
export function turnFromRun(run: ObservedRun): Turn {
  const blocks: Block[] = [];
  const metrics: Record<string, ModelMetrics> = {};
  let modelStep = 0;
  const finalText = (run.nodes.find(node => node.kind === 'output')?.output as string | undefined) ?? '';

  for (const node of run.nodes) {
    if (node.kind === 'tool') {
      const call = callFromNode(node);
      const previous = blocks[blocks.length - 1];
      if (previous?.kind === 'tools') {
        const existing = previous.calls.find(item => item.call_id === call.call_id);
        // 审批等待产生的中间步骤用最终结果覆盖，用户只看到一次调用。
        if (existing) Object.assign(existing, call);
        else previous.calls.push(call);
      } else {
        blocks.push({ kind: 'tools', calls: [call] });
      }
      continue;
    }
    const text = typeof node.output === 'string' ? node.output : '';
    if (node.kind === 'thought') {
      modelStep++;
      const value = readMetrics(node.metrics);
      if (value) metrics[String(modelStep)] = value;
      // 模型最后一个步骤的正文与最终输出节点内容相同，只保留一份。
      if (text.trim() && text.trim() !== finalText.trim()) blocks.push({ kind: 'text', text, streaming: false, activity: 'thought' });
      continue;
    }
    if (node.kind === 'output') {
      if (text.trim()) blocks.push({ kind: 'text', text, streaming: false });
      continue;
    }
    if (node.kind === 'result') blocks.push({ kind: 'text', text: node.error?.message ?? text, streaming: false, activity: 'step' });
  }
  return {
    id: run.id,
    input: run.input,
    status: statusFromApi(run.status),
    blocks,
    error: run.status === 'failed' ? run.nodes.find(node => node.kind === 'result')?.error?.message ?? '' : '',
    tokens: run.totalTokens ?? 0,
    metrics,
    seq: 0,
  };
}

export const useChat = defineStore('chat', () => {
  const workspaces = ref<Workspace[]>([]);
  const workspaceId = ref(readJSON<string>(STORAGE_KEYS.workspace) ?? '');
  const sessionGroups = ref<Record<string, SessionGroup>>({});
  const projectErrors = ref<Record<string, string>>({});
  const projectLoading = ref<Record<string, boolean>>({});
  const sessions = computed({
    get: () => sessionGroups.value[workspaceId.value]?.active ?? [],
    set: (active: Session[]) => { sessionGroups.value[workspaceId.value] = { archived: archivedSessions.value, active }; },
  });
  const archivedSessions = computed({
    get: (): Session[] => sessionGroups.value[workspaceId.value]?.archived ?? [],
    set: (archived: Session[]) => { sessionGroups.value[workspaceId.value] = { active: sessions.value, archived }; },
  });
  const sessionId = ref('');
  const turns = ref<Turn[]>([]);
  const connected = ref(false);
  const busy = ref(false);
  const activeRunId = ref('');
  const error = ref('');
  const streamDegraded = ref(false);
  const temporary = ref(false);
  const selectedSkills = ref<string[]>([]);
  const skills = ref<{ id: string; name: string; enabled: boolean }[]>([]);
  let temporaryId = '';
  let temporaryVersion = 0;
  let temporaryAbort: AbortController | undefined;

  async function loadSkills(): Promise<void> {
    const data = await request<{ items: typeof skills.value }>('/v1/skills');
    if (!Array.isArray(data.items)) throw new ApiError('技能列表格式不正确，请重启本地服务。');
    skills.value = data.items;
    selectedSkills.value = selectedSkills.value.filter(id => skills.value.some(skill => skill.id === id && skill.enabled));
  }

  function endTemporary(): void {
    temporaryVersion++;
    temporaryAbort?.abort();
    if (temporaryId) void fetch(`/v1/temporary-chats/${temporaryId}/end`, { method: 'POST', keepalive: true }).catch(() => {});
    temporaryId = '';
    temporary.value = false;
    turns.value = [];
    activeRunId.value = '';
    error.value = '';
  }

  function beginTemporary(): void {
    closeStream?.(); closeStream = null; stopWatchdog(); endTemporary();
    workspaceId.value = ''; sessionId.value = ''; temporary.value = true;
    streamDegraded.value = false;
  }

  async function sendTemporary(input: string): Promise<void> {
    const version = temporaryVersion;
    if (!temporaryId) {
      const created = await request<{ id: string }>('/v1/temporary-chats', { method: 'POST' });
      if (version !== temporaryVersion) {
        void fetch(`/v1/temporary-chats/${created.id}/end`, { method: 'POST', keepalive: true }).catch(() => {});
        return;
      }
      temporaryId = created.id;
    }
    const id = `${temporaryId}-${Date.now()}`;
    turns.value.push({ id, input, status: 'running', blocks: [], error: '', tokens: 0, seq: 0 });
    activeRunId.value = id;
    temporaryAbort = new AbortController();
    try {
      const response = await fetch(`/v1/temporary-chats/${temporaryId}/messages`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: temporaryAbort.signal,
        body: JSON.stringify({ input, skill_ids: selectedSkills.value }),
      });
      if (!response.ok || !response.body) throw new Error('临时对话不可用，请结束后重新开始。');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = ''; let completed = false;
      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done || version !== temporaryVersion) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split('\n\n'); buffer = frames.pop() ?? '';
          for (const frame of frames) {
            const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5)).join('\n');
            if (!data) continue;
            const event = JSON.parse(data) as RunEvent;
            if (event.type === 'error') throw new Error(String(event.message));
            applyEvent(id, event);
            if (event.type === 'run.end') completed = true;
          }
        }
        if (!completed && version === temporaryVersion) throw new Error('连接已中断，请结束临时对话后重新开始。');
      } finally { await reader.cancel(); }
    } catch (caught) {
      if (version !== temporaryVersion) return;
      const turn = turnById(id);
      if (turn) { turn.status = 'failed'; turn.error = (caught as Error).message; }
      throw caught;
    } finally { if (version === temporaryVersion) activeRunId.value = ''; }
  }

  let closeStream: (() => void) | null = null;
  let watchdog: ReturnType<typeof setInterval> | undefined;

  const workspace = computed(() => workspaces.value.find(item => item.id === workspaceId.value));
  const session = computed(() => [...sessions.value, ...archivedSessions.value].find(item => item.id === sessionId.value));
  const running = computed(() => activeRunId.value !== '');

  async function attempt<T>(work: () => Promise<T>): Promise<T | undefined> {
    busy.value = true;
    try {
      const value = await work();
      error.value = '';
      return value;
    } catch (caught) {
      error.value = (caught as Error).message;
      return undefined;
    } finally {
      busy.value = false;
    }
  }

  async function load(): Promise<void> {
    await attempt(async () => {
      workspaces.value = (await request<{ items: Workspace[] }>('/v1/workspaces')).items;
      connected.value = true;
      const preferred = workspaces.value.some(item => item.id === workspaceId.value)
        ? workspaceId.value
        : workspaces.value[0]?.id ?? '';
      await selectWorkspace(preferred);
      if (preferred) await loadWorkspaceSessions('');
    });
    connected.value = error.value === '';
  }

  async function selectWorkspace(id: string): Promise<void> {
    closeStream?.();
    closeStream = null;
    workspaceId.value = id;
    writeJSON(STORAGE_KEYS.workspace, id);
    sessionId.value = '';
    turns.value = [];
    activeRunId.value = '';
    stopWatchdog();

    const wid = id;
    await loadWorkspaceSessions(wid);
    if (workspaceId.value !== wid) return;
    const stored = readJSON<string>(STORAGE_KEYS.session);
    const next = sessions.value.find(item => item.id === stored)?.id ?? sessions.value[0]?.id ?? '';
    if (next) await selectSession(next);
  }

  async function loadWorkspaceSessions(id: string): Promise<void> {
    projectLoading.value[id] = true;
    projectErrors.value[id] = '';
    try {
      const [active, archived] = await Promise.all([listSessions(id, false), listSessions(id, true)]);
      sessionGroups.value[id] = {
        active: active.filter(item => item.workspace_id === id && !item.archived),
        archived: archived.filter(item => item.workspace_id === id && item.archived === 1),
      };
    } catch (caught) {
      projectErrors.value[id] = (caught as Error).message;
      throw caught;
    } finally {
      projectLoading.value[id] = false;
    }
  }

  async function listSessions(workspaceId: string, archived: boolean): Promise<Session[]> {
    const data = await request<{ items: Session[] }>(
      `/v1/sessions?workspace_id=${encodeURIComponent(workspaceId)}&archived=${archived}`,
    );
    return data.items;
  }

  async function selectSession(id: string): Promise<void> {
    if (id && ![...sessions.value, ...archivedSessions.value].some(item => item.id === id)) {
      throw new ApiError('该会话不属于当前工作区，或已被删除。');
    }
    closeStream?.();
    closeStream = null;
    stopWatchdog();
    activeRunId.value = '';
    sessionId.value = id;
    writeJSON(STORAGE_KEYS.session, id);
    turns.value = [];
    if (id) await loadTurns();
  }

  async function loadTurns(): Promise<void> {
    const sid = sessionId.value;
    if (!sid) return;
    const data = await request<{ items: ObservedRun[] }>(`/v1/runs?conversation_id=${encodeURIComponent(sid)}`);
    if (sessionId.value !== sid) return;
    turns.value = selectSessionRuns(data.items, sid).reverse().map(turnFromRun);
  }

  async function createWorkspace(body: { path: string; name?: string; create?: boolean }): Promise<void> {
    await attempt(async () => {
      const created = await request<Workspace>('/v1/workspaces', { method: 'POST', body: JSON.stringify(body) });
      workspaces.value = [created, ...workspaces.value.filter(item => item.id !== created.id)];
      await selectWorkspace(created.id);
    });
  }

  async function newSession(title = DEFAULT_SESSION_TITLE): Promise<Session> {
    const created = await request<Session>('/v1/sessions', {
      method: 'POST',
      body: JSON.stringify({ workspace_id: workspaceId.value, title: title.trim() || DEFAULT_SESSION_TITLE }),
    });
    sessions.value = [created, ...sessions.value.filter(item => item.id !== created.id)];
    await selectSession(created.id);
    return created;
  }

  /**
   * 会话写操作：后端与前端版本不一致时给出可执行的提示，
   * 而不是让用户对着 404 猜原因。
   */
  async function sessionMutation<T>(path: string, init: RequestInit): Promise<T> {
    try {
      return await request<T>(path, init);
    } catch (caught) {
      const status = (caught as ApiError).status;
      if (status === 404 || status === 405) {
        throw new ApiError('服务端不支持会话管理，请重启本地服务后重试。', status);
      }
      throw caught;
    }
  }

  async function renameSession(id: string, title: string): Promise<void> {
    const updated = await sessionMutation<Session>(`/v1/sessions/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
    sessions.value = sessions.value.map(item => (item.id === id ? updated : item));
    archivedSessions.value = archivedSessions.value.map(item => (item.id === id ? updated : item));
  }

  async function archiveSession(id: string, archived = true, wid = workspaceId.value): Promise<void> {
    await attempt(async () => {
      await sessionMutation<Session>(`/v1/sessions/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify({ archived }),
      });
      const group = sessionGroups.value[wid];
      if (group && archived) {
        const moving = group.active.find(item => item.id === id);
        group.active = group.active.filter(item => item.id !== id);
        if (moving) group.archived = [{ ...moving, archived: 1 }, ...group.archived];
      } else if (group) {
        const moving = group.archived.find(item => item.id === id);
        group.archived = group.archived.filter(item => item.id !== id);
        if (moving) group.active = [{ ...moving, archived: 0 }, ...group.active];
      }
      // 归档 / 恢复当前会话后，始终落在一个可见的会话上。
      if (workspaceId.value === wid && sessionId.value === id) {
        await selectSession(archived ? sessions.value[0]?.id ?? '' : id);
      }
    });
  }

  async function deleteSession(id: string, wid = workspaceId.value): Promise<void> {
    await attempt(async () => {
      await sessionMutation(`/v1/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' });
      const wasCurrent = workspaceId.value === wid && sessionId.value === id;
      const group = sessionGroups.value[wid];
      if (group) {
        group.active = group.active.filter(item => item.id !== id);
        group.archived = group.archived.filter(item => item.id !== id);
      }
      if (wasCurrent) await selectSession(sessions.value[0]?.id ?? '');
    });
  }

  async function send(text: string): Promise<void> {
    await attempt(async () => {
      const input = text.trim();
      if (!input) return;
      if (temporary.value) { await sendTemporary(input); return; }
      if (!sessionId.value) await newSession();
      const active = sessions.value.find(item => item.id === sessionId.value);

      const submission = await request<Submission>('/v1/runs', {
        method: 'POST',
        body: JSON.stringify({ input, workspace_id: workspaceId.value || undefined, conversation_id: sessionId.value,
          ...(selectedSkills.value.length ? { skill_ids: selectedSkills.value } : {}) }),
      });

      // 会话标题跟着第一条指令走，否则侧栏会堆满同名的「新任务」。
      if (active && active.title === DEFAULT_SESSION_TITLE) await renameSession(active.id, titleFrom(input));

      turns.value.push({ id: submission.run_id, input, status: submission.blocked ? 'failed' : 'running', blocks: [], error: '', tokens: 0, seq: 0 });
      if (submission.blocked) {
        pushTextBlock(submission.run_id, submission.output ?? '请求被安全策略阻止。');
        return;
      }
      activeRunId.value = submission.run_id;
      openStream(submission.run_id);
    });
  }

  function openStream(runId: string): void {
    closeStream?.();
    streamDegraded.value = false;
    startWatchdog(runId);
    closeStream = streamRun(runId, {
      onEvent: event => {
        applyEvent(runId, event);
        if (event.type === 'run.end') {
          closeStream?.();
          closeStream = null;
          stopWatchdog();
          activeRunId.value = '';
          void attempt(() => loadTurns());
        }
      },
      onError: message => {
        // 事件流不可用时不再清空进行中的 Run：看门狗会轮询并保证结果最终一致。
        streamDegraded.value = true;
        error.value = message;
      },
    });
  }

  /**
   * 兜底轮询：SSE 断线、代理缓冲、或对面是没有 /stream 的旧服务时，
   * 仍然要让文本与工具调用收敛到服务端真相，而不是永远停在半截。
   */
  function startWatchdog(runId: string): void {
    stopWatchdog();
    watchdog = setInterval(() => { void syncActiveRun(runId); }, 2000);
  }

  function stopWatchdog(): void {
    if (watchdog !== undefined) clearInterval(watchdog);
    watchdog = undefined;
  }

  async function syncActiveRun(runId: string): Promise<void> {
    if (activeRunId.value !== runId || !sessionId.value) return;
    const sid = sessionId.value;
    let run: ObservedRun | undefined;
    try {
      const data = await request<{ items: ObservedRun[] }>(`/v1/runs?conversation_id=${encodeURIComponent(sid)}`);
      run = selectSessionRuns(data.items, sid).find(item => item.id === runId);
    } catch {
      return;   // 下一轮再试
    }
    if (!run || sessionId.value !== sid) return;

    const turn = turnById(runId);
    if (turn && !turn.seq) {
      // 一条事件都没收到（流不可用）：直接用服务端视图补齐文本与工具气泡。
      const rebuilt = turnFromRun(run);
      turn.blocks = rebuilt.blocks;
      turn.status = rebuilt.status;
      turn.tokens = rebuilt.tokens;
      turn.metrics = rebuilt.metrics;
      streamDegraded.value = true;
    }
    if (!ACTIVE_RUN_STATUSES.has(run.status)) {
      stopWatchdog();
      activeRunId.value = '';
      closeStream?.();
      closeStream = null;
      await attempt(() => loadTurns());
    }
  }

  function pushTextBlock(runId: string, text: string): void {
    const turn = turnById(runId);
    if (turn) turn.blocks.push({ kind: 'text', text, streaming: false });
  }

  function turnById(runId: string): Turn | undefined {
    return turns.value.find(item => item.id === runId);
  }

  function lastTextBlock(turn: Turn): TextBlock | undefined {
    const last = turn.blocks[turn.blocks.length - 1];
    return last && last.kind === 'text' ? last : undefined;
  }

  function pushCall(turn: Turn, call: ToolCallView): void {
    const last = turn.blocks[turn.blocks.length - 1];
    if (last?.kind === 'tools') last.calls.push(call);
    else turn.blocks.push({ kind: 'tools', calls: [call] });
  }

  function findCall(turn: Turn, callId: string): ToolCallView | undefined {
    for (let index = turn.blocks.length - 1; index >= 0; index -= 1) {
      const block = turn.blocks[index];
      if (block.kind !== 'tools') continue;
      const call = block.calls.find(item => item.call_id === callId);
      if (call) return call;
    }
    return undefined;
  }

  /** 单条 SSE 事件 → 轮次状态的增量更新（按 seq 幂等）。 */
  function applyEvent(runId: string, event: RunEvent): void {
    const turn = turnById(runId);
    if (!turn) return;

    const seq = Number(event.seq ?? 0);
    if (seq && seq <= turn.seq) return;   // 重连后的重放帧不重复计入
    if (seq) turn.seq = seq;

    switch (event.type) {
      case 'model.start':
        turn.blocks.push({ kind: 'text', text: '', streaming: true, activity: 'thought' });
        return;
      case 'model.delta': {
        const chunk = typeof event.text === 'string' ? event.text : '';
        if (!chunk) return;
        let block = lastTextBlock(turn);
        if (!block || !block.streaming) {
          turn.blocks.push({ kind: 'text', text: '', streaming: true, activity: 'thought' });
          block = lastTextBlock(turn)!;
        }
        block.text += chunk;
        return;
      }
      case 'model.end': {
        const metrics = readMetrics(event.metrics);
        if (metrics) {
          turn.metrics ??= {};
          turn.metrics[String(event.step ?? Object.keys(turn.metrics).length + 1)] = metrics;
        }
        const text = typeof event.text === 'string' ? event.text : '';
        const calls = Array.isArray(event.tool_calls) ? event.tool_calls : [];
        const block = lastTextBlock(turn);
        if (block) {
          block.text = text || block.text;
          block.streaming = false;
          block.activity = calls.length ? 'thought' : undefined;
          if (!block.text.trim() && turn.blocks[turn.blocks.length - 1] === block) turn.blocks.pop();
        } else if (text.trim()) {
          turn.blocks.push({ kind: 'text', text, streaming: false, activity: calls.length ? 'thought' : undefined });
        }
        turn.tokens += Number(event.tokens ?? 0) || 0;
        for (const raw of calls) {
          const call = raw as { call_id?: string; name?: string; arguments?: Record<string, unknown> };
          pushCall(turn, {
            call_id: String(call.call_id ?? ''),
            name: String(call.name ?? '工具'),
            arguments: call.arguments ?? {},
            state: 'running',
            status: 'running',
            output: '',
            diff: null,
          });
        }
        return;
      }
      case 'tool.start': {
        const callId = String(event.call_id ?? '');
        const existing = findCall(turn, callId);
        if (existing) { existing.state = 'running'; existing.status = 'running'; return; }
        pushCall(turn, {
          call_id: callId,
          name: String(event.name ?? '工具'),
          arguments: (event.arguments ?? {}) as Record<string, unknown>,
          state: 'running',
          status: 'running',
          output: '',
          diff: null,
        });
        return;
      }
      case 'tool.end': {
        const callId = String(event.call_id ?? '');
        const status = String(event.status ?? 'success');
        const parsed = parseToolResult(event.output);
        const call = findCall(turn, callId);
        if (call) {
          call.state = toolState(status);
          call.status = status;
          call.output = parsed.text;
          call.diff = parsed.diff;
        } else {
          pushCall(turn, {
            call_id: callId, name: String(event.name ?? '工具'), arguments: {},
            state: toolState(status), status, output: parsed.text, diff: parsed.diff,
          });
        }
        return;
      }
      case 'phase':
        turn.status = statusFromApi(String(event.phase ?? 'running'));
        return;
      case 'run.waiting': {
        turn.status = 'waiting';
        const callId = String(event.call_id ?? '');
        const call = findCall(turn, callId);
        if (call) { call.state = 'waiting'; call.status = 'approval_required'; return; }
        pushCall(turn, {
          call_id: callId || `waiting-${turn.blocks.length}`,
          name: String(event.tool_name ?? '工具'),
          arguments: (event.arguments ?? {}) as Record<string, unknown>,
          state: 'waiting', status: 'approval_required', output: '', diff: null,
        });
        return;
      }
      case 'run.end': {
        const status = String(event.status ?? 'completed');
        turn.status = statusFromApi(status);
        const output = typeof event.output === 'string' ? event.output : '';
        if (output.trim()) {
          const block = lastTextBlock(turn);
          if (block && (!block.activity || block.text.trim() === output.trim())) {
            block.text = output;
            block.streaming = false;
            block.activity = undefined;
          }
          else turn.blocks.push({ kind: 'text', text: output, streaming: false });
        }
        if (typeof event.error === 'string' && event.error) turn.error = event.error;
        for (const block of turn.blocks) if (block.kind === 'text') block.streaming = false;
        return;
      }
      default:
        return;
    }
  }

  async function approve(runId: string): Promise<void> {
    await attempt(async () => {
      await request(`/v1/runs/${encodeURIComponent(runId)}/approve`, { method: 'POST' });
      const turn = turnById(runId);
      if (!turn) return;
      turn.status = 'running';
      for (const block of turn.blocks) {
        if (block.kind !== 'tools') continue;
        for (const call of block.calls) if (call.state === 'waiting') { call.state = 'running'; call.status = 'running'; }
      }
      if (!activeRunId.value) { activeRunId.value = runId; openStream(runId); }
    });
  }

  async function reject(runId: string): Promise<void> {
    await attempt(async () => {
      await request(`/v1/runs/${encodeURIComponent(runId)}/reject`, { method: 'POST' });
    });
  }

  async function cancel(runId: string): Promise<void> {
    await attempt(async () => {
      await request(`/v1/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' });
    });
  }

  return {
    temporary, selectedSkills, skills, loadSkills, beginTemporary, endTemporary,
    workspaces, workspaceId, workspace, sessions, archivedSessions, sessionId, session, turns,
    sessionGroups, projectErrors, projectLoading, loadWorkspaceSessions,
    connected, busy, error, streamDegraded, activeRunId, running,
    load, selectWorkspace, selectSession, loadTurns, createWorkspace,
    newSession, renameSession, archiveSession, deleteSession, send, approve, reject, cancel, attempt,
  };
});
