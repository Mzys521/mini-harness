<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import MarkdownText from '@/components/MarkdownText.vue';
import ToolCallCard from '@/components/ToolCallCard.vue';
import WorkspaceCreator from '@/components/WorkspaceCreator.vue';
import AppIcon from '@/components/AppIcon.vue';
import ActivityRow from '@/components/ActivityRow.vue';
import AppearanceSettings from '@/components/AppearanceSettings.vue';
import { useAppearance } from '@/stores/appearance';
import ResizeDivider from '@/components/ResizeDivider.vue';
import { LAYOUT_DEFAULTS, usePanelLayout } from '@/composables/usePanelLayout';
import { STATUS_LABELS, useChat } from '@/stores/chat';
import { onStorageUnavailable } from '@/api/storage';
import ProjectTree from '@/components/ProjectTree.vue';
import CapabilityPage from '@/components/CapabilityPage.vue';
import PersonalPage from '@/components/PersonalPage.vue';
import ChatList from '@/components/ChatList.vue';
import ConversationMetrics from '@/components/ConversationMetrics.vue';
import ConversationLocator from '@/components/ConversationLocator.vue';
import { chatHref, NAV_PAGES, useWorkbenchRoute } from '@/composables/useWorkbenchRoute';

const chat = useChat();
const { route, navigate } = useWorkbenchRoute();
const ready = ref(false);
const routeError = ref('');
let routeVersion = 0;
let applyingRoute = false;
const root = ref<HTMLElement | null>(null);
const main = ref<HTMLElement | null>(null);
const { narrow, sidebarSize, sidebarMin, sidebarMax, sidebarDefault, composerSize, composerMin, composerMax, save: saveLayout } = usePanelLayout(root, main);
useAppearance();
const settingsOpen = ref(false);
const settingsSection = ref<'appearance' | 'preferences'>('appearance');
const logoUrl = `${import.meta.env.BASE_URL}icon.svg`;
const draft = ref('');
const creating = ref(false);
const storageWarning = ref('');
const scroller = ref<HTMLElement | null>(null);
const follow = ref(true);
const pendingDelete = ref('');
const pendingWorkspace = ref('');
const deleteError = ref('');

const canSend = computed(() => draft.value.trim().length > 0 && ready.value && chat.connected && !chat.running && !chat.busy);
const isChatRoute = computed(() => route.value.page === 'chat' || route.value.page === 'temporary');
const progress = computed(() => chat.turns.map(turn => `${turn.id}:${turn.status}:${turn.blocks.length}`).join('|'));
const deleting = computed(() => {
  const group = chat.sessionGroups[pendingWorkspace.value];
  return [...(group?.active ?? []), ...(group?.archived ?? [])].find(item => item.id === pendingDelete.value);
});

function askDelete(id: string, workspace: string): void {
  pendingDelete.value = id;
  pendingWorkspace.value = workspace;
  deleteError.value = '';
}

/** 删除会连带清掉该会话的 Run、步骤与消息，因此必须二次确认。 */
async function confirmDelete(): Promise<void> {
  const id = pendingDelete.value;
  if (!id) return;
  await chat.deleteSession(id, pendingWorkspace.value);
  if (chat.error) deleteError.value = chat.error;
  else pendingDelete.value = '';
}

async function archive(id: string, archived: boolean, workspace: string): Promise<void> {
  await chat.archiveSession(id, archived, workspace);
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

async function newSession(workspace = ''): Promise<void> {
  if (chat.temporary) chat.endTemporary();
  draft.value = '';
  applyingRoute = true;
  await chat.attempt(async () => {
    if (workspace !== chat.workspaceId) await chat.selectWorkspace(workspace);
    await chat.newSession();
  });
  applyingRoute = false;
  navigate(chatHref(chat.workspaceId, chat.sessionId));
  await nextTick();
  toBottom();
}

async function applyRoute(): Promise<void> {
  if (!ready.value) return;
  const version = ++routeVersion;
  const target = route.value;
  routeError.value = '';
  applyingRoute = true;
  const leavingTemporary = chat.temporary;
  try {
    if (target.page === 'preferences') {
      settingsSection.value = 'preferences'; settingsOpen.value = true;
      navigate(chat.temporary ? '#/temporary' : chatHref(chat.workspaceId, chat.sessionId), true);
      return;
    }
    if (target.page === 'temporary') {
      if (!chat.temporary) { chat.beginTemporary(); draft.value = ''; }
      return;
    }
    if (chat.temporary) { chat.endTemporary(); draft.value = ''; }
    if (target.page !== 'chat') return;
    const workspace = target.workspace;
    if (workspace && !chat.workspaces.some(item => item.id === workspace)) throw new Error('找不到这个项目，请从左侧选择已有项目。');
    if (!leavingTemporary && chat.busy && (workspace !== chat.workspaceId || (target.session && target.session !== chat.sessionId))) throw new Error('当前请求正在处理中，请稍后重试。');
    if (workspace !== chat.workspaceId || !chat.sessionGroups[workspace]) await chat.selectWorkspace(workspace);
    if (version !== routeVersion) return;
    if (target.session && ![...(chat.sessionGroups[workspace]?.active ?? []), ...(chat.sessionGroups[workspace]?.archived ?? [])].some(item => item.id === target.session)) await chat.loadWorkspaceSessions(workspace);
    if (version !== routeVersion) return;
    if (target.session && target.session !== chat.sessionId) await chat.selectSession(target.session);
    if (version !== routeVersion) return;
    navigate(chatHref(chat.workspaceId, chat.sessionId), true);
    await nextTick();
    toBottom();
  } catch (caught) {
    if (version === routeVersion) routeError.value = (caught as Error).message;
  } finally { if (version === routeVersion) applyingRoute = false; }
}
watch(route, applyRoute);
watch(() => [chat.workspaceId, chat.sessionId, chat.busy] as const, () => {
  if (ready.value && !applyingRoute && !chat.busy && !routeError.value && route.value.page === 'chat') navigate(chatHref(chat.workspaceId, chat.sessionId), true);
});

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
  void chat.loadSkills().catch(() => {});
  ready.value = true;
  await applyRoute();
  await nextTick();
  toBottom();
});
function endTemporary(): void { chat.endTemporary(); draft.value = ''; navigate(chatHref()); }
function pageHide(): void { if (chat.temporary) { chat.endTemporary(); draft.value = ''; } }
window.addEventListener('pagehide', pageHide);
onUnmounted(() => { window.removeEventListener('pagehide', pageHide); pageHide(); });
</script>

<template>
  <div ref="root" class="app" :style="{ '--sidebar-size': `${sidebarSize}px`, '--composer-size': `${composerSize}px` }">
    <aside id="workspace-sidebar" class="sidebar">
      <div class="brand">
        <img :src="logoUrl" class="brand-logo" alt="Mini Harness Logo" width="36" height="36" />
        <div><strong>Mini Harness</strong><small>mini-harness · 本地工作区</small></div>
      </div>

      <div class="sidebar-content">
        <nav class="workspace-nav" aria-label="主导航">
          <button type="button" :disabled="chat.busy || !ready" @click="newSession()"><AppIcon name="edit" /><span>新对话</span></button>
          <a v-for="page in NAV_PAGES" :key="page.id" :href="`#/${page.id}`" :aria-current="route.page === page.id ? 'page' : undefined" @click.prevent="navigate(`#/${page.id}`)"><AppIcon :name="page.icon" /><span>{{ page.label }}</span></a>
        </nav>
        <ProjectTree :in-chat="route.page === 'chat' && !routeError" @open="navigate" @create="creating = true" @new-session="newSession" @archive="archive" @delete="askDelete" />
        <ChatList :active="route.page === 'chat' && !chat.workspaceId" @open="navigate" @create="newSession()" @delete="askDelete" />

      </div>
      <footer class="side-foot">
        <button type="button" class="settings-profile" aria-label="设置" title="设置" @click="settingsSection = 'appearance'; settingsOpen = true">
          <img :src="logoUrl" alt="" width="32" height="32" />
          <span class="settings-profile-copy"><strong>设置</strong><small><span class="dot" :class="{ online: chat.connected }" />{{ chat.connected ? '本地服务已连接' : '未连接本地服务' }}</small></span>
          <AppIcon name="settings" />
        </button>
      </footer>
    </aside>

    <ResizeDivider :key="narrow ? 'stacked' : 'columns'" v-model="sidebarSize" :min="sidebarMin" :max="sidebarMax" :default-value="sidebarDefault"
      :orientation="narrow ? 'horizontal' : 'vertical'" :label="narrow ? '调整侧栏高度' : '调整侧栏宽度'" controls="workspace-sidebar" @commit="saveLayout" />

    <main ref="main" class="main">
      <PersonalPage v-if="route.page === 'skills' || route.page === 'automations'" :page="route.page" @open="navigate" />
      <CapabilityPage v-else-if="!isChatRoute" :page="route.page" @back="navigate(chatHref(chat.workspaceId, chat.sessionId))" />
      <section v-if="route.page === 'chat' && routeError" class="route-page"><h1>无法打开对话</h1><p class="error">{{ routeError }}</p><button type="button" @click="applyRoute">重试</button><button type="button" @click="navigate(chatHref(chat.workspaceId, chat.sessionId))">返回项目对话</button></section>
      <section v-show="isChatRoute && !routeError" class="conversation-view" :class="{ 'temporary-chat': chat.temporary }" :aria-label="chat.temporary ? '临时对话' : chat.workspaceId ? '项目对话' : '普通对话'">
      <header class="topbar">
        <div class="topbar-title">
          <strong>{{ chat.temporary ? '临时对话' : chat.session?.title ?? '开始一段新对话' }}</strong>
          <small v-if="chat.workspace">{{ chat.workspace.name }} · <span class="mono">{{ chat.workspace.path }}</span></small>
          <small v-else>{{ chat.temporary ? '结束后清除 · 不写入长期记忆' : '普通对话 · 无需工作区' }}</small>
        </div>
        <div class="topbar-actions">
          <button v-if="chat.temporary" type="button" class="temporary-toggle" aria-label="结束临时对话" title="结束临时对话" :aria-pressed="true" @click="endTemporary"><AppIcon name="temporary" /></button>
          <button v-else-if="!chat.workspaceId" type="button" class="temporary-toggle" aria-label="临时对话" title="临时对话" :aria-pressed="false" :disabled="chat.busy || chat.running" @click="navigate('#/temporary')"><AppIcon name="temporary" /></button>
          <span v-if="chat.running" class="running"><span class="dot online" />运行中</span>
        </div>
      </header>

      <div class="transcript-shell">
      <div ref="scroller" class="transcript" @scroll.passive="onScroll">
        <div v-if="!chat.turns.length" class="welcome">
          <h1>{{ chat.temporary ? '此刻聊，结束即清除。' : chat.workspaceId ? '在工作区里对话。' : '从一个想法开始。' }}</h1>
          <p>{{ chat.temporary ? '读取你的使用习惯；结束、离开、刷新或关闭页面后清除本地会话，不新增长期记忆。' : chat.workspaceId ? '描述目标与约束。Agent 会读取代码、提出修改，并在写入文件或执行命令前等待你批准。' : '自由提问，无需创建项目。保存的使用习惯会随每次对话加载。' }}</p>
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
      <ConversationLocator :turns="chat.turns" :scroller="scroller" @navigate="follow = false" />
      </div>

      <p v-if="chat.error" class="error banner">{{ chat.error }}</p>
      <p v-if="chat.streamDegraded" class="hint banner">实时事件流不可用，已切换为轮询同步（结果不会丢失）。</p>
      <p v-if="storageWarning" class="hint banner">{{ storageWarning }}</p>

      <ResizeDivider v-model="composerSize" :min="composerMin" :max="composerMax" :default-value="LAYOUT_DEFAULTS.composerHeight"
        orientation="horizontal" label="调整输入区高度" controls="message-composer" reverse @commit="saveLayout" />
      <form id="message-composer" class="composer" @submit.prevent="submit">
        <div class="composer-card">
          <textarea
            v-model="draft"
            rows="3"
            spellcheck="false"
            aria-label="消息"
            :disabled="chat.running"
            placeholder="描述你想完成的事情…"
            @keydown="onKeydown"
          />
          <div class="composer-foot">
            <span class="composer-approval"><AppIcon name="shield" /><span>{{ chat.temporary ? '临时对话' : '写入需批准' }}</span></span>
            <details class="composer-skills" @toggle="($event.target as HTMLDetailsElement).open && chat.loadSkills().catch(() => {})"><summary><AppIcon name="skill" />技能{{ chat.selectedSkills.length ? ` · ${chat.selectedSkills.length}` : '' }}</summary><div class="skill-popover"><p v-if="!chat.skills.some(item => item.enabled)" class="hint">在左侧“技能”中创建或导入 SKILL.md。</p><label v-for="skill in chat.skills.filter(item => item.enabled)" :key="skill.id" class="checkbox"><input v-model="chat.selectedSkills" type="checkbox" :value="skill.id" :disabled="chat.running || (!chat.selectedSkills.includes(skill.id) && chat.selectedSkills.length >= 8)" />{{ skill.name }}</label></div></details>
            <span class="composer-shortcut">Enter 发送 · Shift + Enter 换行</span>
            <button v-if="chat.activeRunId" type="button" class="composer-send" aria-label="停止运行" title="停止运行" :disabled="chat.busy && !chat.temporary" @click="chat.temporary ? endTemporary() : chat.cancel(chat.activeRunId)"><AppIcon name="stop" /></button>
            <button v-else type="submit" class="composer-send" :aria-label="chat.busy ? '提交中' : '发送'" :title="chat.busy ? '提交中…' : '发送消息'" :disabled="!canSend"><AppIcon name="arrow-up" /></button>
          </div>
        </div>
      </form>
      <ConversationMetrics :turns="chat.turns" />
      </section>
    </main>

    <AppearanceSettings v-if="settingsOpen" :initial-section="settingsSection" @close="settingsOpen = false" />

    <div v-if="creating" class="overlay" @click.self="creating = false">
      <WorkspaceCreator @close="creating = false" @created="navigate(chatHref(chat.workspaceId, chat.sessionId))" />
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
