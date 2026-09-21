<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import MarkdownText from '@/components/MarkdownText.vue';
import ToolCallCard from '@/components/ToolCallCard.vue';
import WorkspaceCreator from '@/components/WorkspaceCreator.vue';
import AppIcon from '@/components/AppIcon.vue';
import ActivityRow from '@/components/ActivityRow.vue';
import AppearanceSettings from '@/components/AppearanceSettings.vue';
import { useAppearance } from '@/stores/appearance';
import { STATUS_LABELS, useChat } from '@/stores/chat';
import { onStorageUnavailable } from '@/api/storage';

const chat = useChat();
useAppearance();
const settingsOpen = ref(false);
const logoUrl = `${import.meta.env.BASE_URL}icon.svg`;
const draft = ref('');
const creating = ref(false);
const storageWarning = ref('');
const scroller = ref<HTMLElement | null>(null);
const follow = ref(true);
const showArchived = ref(false);
const pendingDelete = ref('');
const deleteError = ref('');

const canSend = computed(() => draft.value.trim().length > 0 && !!chat.workspaceId && !chat.running && !chat.busy);
const progress = computed(() => chat.turns.map(turn => `${turn.id}:${turn.status}:${turn.blocks.length}`).join('|'));
const deleting = computed(() => chat.sessions.find(item => item.id === pendingDelete.value)
  ?? chat.archivedSessions.find(item => item.id === pendingDelete.value));

function askDelete(id: string): void {
  pendingDelete.value = id;
  deleteError.value = '';
}

/** 删除会连带清掉该会话的 Run、步骤与消息，因此必须二次确认。 */
async function confirmDelete(): Promise<void> {
  const id = pendingDelete.value;
  if (!id) return;
  await chat.deleteSession(id);
  if (chat.error) deleteError.value = chat.error;
  else pendingDelete.value = '';
}

async function archive(id: string, archived: boolean): Promise<void> {
  await chat.archiveSession(id, archived);
}

function toBottom(): void {
  follow.value = true;
  const element = scroller.value;
  if (element) element.scrollTop = element.scrollHeight;
}

function onScroll(): void {
  const element = scroller.value;
  if (!element) return;
  follow.value = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
}

async function submit(): Promise<void> {
  const text = draft.value.trim();
  if (!text || !canSend.value) return;
  draft.value = '';
  await chat.send(text);
  if (chat.error) draft.value = text;
  await nextTick();
  toBottom();
}

function onKeydown(event: KeyboardEvent): void {
  // Shift+Enter keeps newlines; Enter inside an IME composition must not submit.
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  void submit();
}

async function openSession(id: string): Promise<void> {
  if (id === chat.sessionId) return;
  await chat.attempt(() => chat.selectSession(id));
  await nextTick();
  toBottom();
}

async function newSession(): Promise<void> {
  await chat.attempt(() => chat.newSession());
  await nextTick();
  toBottom();
}

watch(progress, async () => {
  if (!follow.value) return;
  await nextTick();
  const element = scroller.value;
  if (element) element.scrollTop = element.scrollHeight;
});

watch(() => chat.sessionId, () => { follow.value = true; });

onMounted(async () => {
  onStorageUnavailable(() => { storageWarning.value = '浏览器存储不可用，本次选择不会被记住。'; });
  await chat.load();
  await nextTick();
  toBottom();
});
</script>

<template>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <img :src="logoUrl" class="brand-logo" alt="Mini Harness Logo" width="36" height="36" />
        <div><strong>Mini Harness</strong><small>mini-harness · 本地工作区</small></div>
      </div>

      <section class="side-section">
        <header>
          <span>工作区</span>
          <button type="button" class="icon" title="新建工作区" @click="creating = true">＋</button>
        </header>
        <ul class="workspace-list">
          <li v-for="item in chat.workspaces" :key="item.id">
            <button type="button" :class="{ active: item.id === chat.workspaceId }" @click="chat.attempt(() => chat.selectWorkspace(item.id))">
              <span class="workspace-name">{{ item.name }}</span>
              <small class="mono" :title="item.path">{{ item.path }}</small>
            </button>
          </li>
        </ul>
        <p v-if="!chat.workspaces.length" class="hint">还没有工作区，先新建一个目录关联。</p>
      </section>

      <section class="side-section grow">
        <header>
          <span>会话</span>
          <button type="button" class="icon" title="新建会话" :disabled="!chat.workspaceId" @click="newSession">＋</button>
        </header>
        <ul class="session-list">
          <li v-for="item in chat.sessions" :key="item.id" :class="{ active: item.id === chat.sessionId }">
            <button type="button" class="session-open" :title="item.title" @click="openSession(item.id)">{{ item.title }}</button>
            <span class="session-actions">
              <button type="button" class="icon" title="归档会话" @click="archive(item.id, true)">归档</button>
              <button type="button" class="icon danger" title="删除会话" @click="askDelete(item.id)">删除</button>
            </span>
          </li>
        </ul>
        <p v-if="chat.workspaceId && !chat.sessions.length" class="hint">这个工作区还没有会话。</p>

        <div v-if="chat.archivedSessions.length" class="archived">
          <button type="button" class="archived-toggle" @click="showArchived = !showArchived">
            {{ showArchived ? '▾' : '▸' }} 已归档 · {{ chat.archivedSessions.length }}
          </button>
          <ul v-if="showArchived" class="session-list">
            <li v-for="item in chat.archivedSessions" :key="item.id">
              <button type="button" class="session-open" :title="item.title" @click="openSession(item.id)">{{ item.title }}</button>
              <span class="session-actions">
                <button type="button" class="icon" title="恢复会话" @click="archive(item.id, false)">恢复</button>
                <button type="button" class="icon danger" title="删除会话" @click="askDelete(item.id)">删除</button>
              </span>
            </li>
          </ul>
        </div>
      </section>

      <footer class="side-foot">
        <span class="dot" :class="{ online: chat.connected }" />
        <span>{{ chat.connected ? '本地服务已连接' : '未连接本地服务' }}</span>
      </footer>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="topbar-title">
          <strong>{{ chat.session?.title ?? '开始一段新对话' }}</strong>
          <small v-if="chat.workspace">{{ chat.workspace.name }} · <span class="mono">{{ chat.workspace.path }}</span></small>
          <small v-else>请先在左侧添加工作区</small>
        </div>
        <div class="topbar-actions">
          <button type="button" class="settings-trigger ghost" aria-label="外观设置" @click="settingsOpen = true"><AppIcon name="settings" /><span>设置</span></button>
          <span v-if="chat.running" class="running"><span class="dot online" />运行中</span>
          <button v-if="chat.activeRunId" type="button" class="ghost" @click="chat.cancel(chat.activeRunId)">停止</button>
        </div>
      </header>

      <div ref="scroller" class="transcript" @scroll.passive="onScroll">
        <div v-if="!chat.turns.length" class="welcome">
          <h1>在工作区里对话。</h1>
          <p>描述目标与约束。Agent 会读取代码、提出修改，并在写入文件或执行命令前等待你批准。</p>
          <button v-if="!chat.workspaceId" type="button" class="primary" @click="creating = true">添加工作区目录</button>
        </div>

        <article v-for="turn in chat.turns" :key="turn.id" class="turn" :data-run="turn.id">
          <p class="user-input">{{ turn.input }}</p>
          <template v-for="(block, index) in turn.blocks" :key="index">
            <ActivityRow v-if="block.kind === 'text' && block.activity" :icon="block.activity === 'thought' ? 'thought' : 'step'" :label="block.activity === 'thought' ? '思考' : '执行步骤'" :preview="block.text.replace(/\s+/g, ' ').trim() || '正在思考…'" :status="block.streaming ? '生成中' : undefined">
              <MarkdownText :text="block.text" :streaming="block.streaming" />
            </ActivityRow>
            <MarkdownText v-else-if="block.kind === 'text'" :text="block.text" :streaming="block.streaming" />
            <div v-else class="tool-group">
              <ToolCallCard v-for="call in block.calls" :key="call.call_id" :call="call" />
            </div>
          </template>
          <div v-if="turn.status === 'waiting'" class="approval">
            <span>该操作需要你的批准才能继续。</span>
            <button type="button" class="primary" @click="chat.approve(turn.id)">批准</button>
            <button type="button" @click="chat.reject(turn.id)">拒绝</button>
          </div>
          <p v-if="turn.error" class="error">{{ turn.error }}</p>
          <p class="turn-foot">
            <span :class="`status-${turn.status}`">{{ STATUS_LABELS[turn.status] }}</span>
            <span v-if="turn.tokens"> · {{ turn.tokens }} tokens</span>
          </p>
        </article>

        <button v-if="!follow" type="button" class="jump" @click="toBottom">回到最新</button>
      </div>

      <p v-if="chat.error" class="error banner">{{ chat.error }}</p>
      <p v-if="chat.streamDegraded" class="hint banner">实时事件流不可用，已切换为轮询同步（结果不会丢失）。</p>
      <p v-if="storageWarning" class="hint banner">{{ storageWarning }}</p>

      <form class="composer" @submit.prevent="submit">
        <textarea
          v-model="draft"
          rows="3"
          spellcheck="false"
          :disabled="!chat.workspaceId || chat.running"
          :placeholder="chat.workspaceId ? '描述任务，例如：检查项目结构并修复登录流程中的问题…' : '请先添加工作区'"
          @keydown="onKeydown"
        />
        <div class="composer-foot">
          <span>Enter 发送 · Shift + Enter 换行 · 写入需批准</span>
          <button type="submit" class="primary" :disabled="!canSend">{{ chat.running ? '运行中…' : chat.busy ? '提交中…' : '发送' }}</button>
        </div>
      </form>
    </main>

    <AppearanceSettings v-if="settingsOpen" @close="settingsOpen = false" />

    <div v-if="creating" class="overlay" @click.self="creating = false">
      <WorkspaceCreator @close="creating = false" />
    </div>

    <div v-if="pendingDelete" class="overlay" @click.self="pendingDelete = ''">
      <section class="creator confirm">
        <header><h2>删除会话</h2></header>
        <p>将永久删除「{{ deleting?.title ?? '该会话' }}」及其全部运行记录（对话、步骤、工具调用与检查点）。此操作不可撤销。</p>
        <p v-if="deleteError" class="error">{{ deleteError }}</p>
        <footer>
          <button type="button" @click="pendingDelete = ''">取消</button>
          <button type="button" class="danger-solid" :disabled="chat.busy" @click="confirmDelete">确认删除</button>
        </footer>
      </section>
    </div>
  </div>
</template>
