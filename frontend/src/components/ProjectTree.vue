<script setup lang="ts">
import { ref, watch } from 'vue';
import AppIcon from './AppIcon.vue';
import { useChat } from '@/stores/chat';
import { chatHref } from '@/composables/useWorkbenchRoute';

defineProps<{ inChat: boolean }>();
const emit = defineEmits<{
  open: [href: string]; create: []; newSession: [workspace: string];
  archive: [id: string, archived: boolean, workspace: string]; delete: [id: string, workspace: string];
}>();
const chat = useChat();
const expanded = ref<Record<string, boolean>>({});
const archived = ref<Record<string, boolean>>({});
watch(() => chat.workspaceId, id => { if (id) expanded.value[id] = true; }, { immediate: true });
watch(() => chat.session, session => {
  if (session?.archived) archived.value[session.workspace_id] = true;
});
async function load(id: string): Promise<void> {
  try { await chat.loadWorkspaceSessions(id); } catch { /* Inline project error provides retry. */ }
}
function toggle(id: string): void {
  expanded.value[id] = !expanded.value[id];
  if (expanded.value[id] && !chat.sessionGroups[id] && !chat.projectLoading[id]) void load(id);
}
</script>

<template>
  <section class="side-section project-tree" aria-label="项目">
    <header><span>项目</span><button type="button" class="icon project-create" title="新建工作区" aria-label="新建工作区" @click="emit('create')"><AppIcon name="plus" /></button></header>
    <p v-if="!chat.workspaces.length" class="hint">添加工作区目录，开始第一个项目。</p>
    <ul class="project-list">
      <li v-for="project in chat.workspaces" :key="project.id" :data-workspace="project.id">
        <div class="project-heading">
          <button type="button" class="project-toggle" :title="project.path" @click="toggle(project.id)">
            <AppIcon name="folder" /><span>{{ project.name }}</span>
          </button>
          <button type="button" class="icon project-add" :aria-label="`在 ${project.name} 新建会话`" title="新建会话" :disabled="chat.busy" @click="emit('newSession', project.id)"><AppIcon name="compose" /></button>
          <button type="button" class="icon project-expand" :aria-label="`${expanded[project.id] ? '收起' : '展开'}项目 ${project.name}`" :aria-expanded="!!expanded[project.id]" :aria-controls="`project-${project.id}`" @click="toggle(project.id)"><AppIcon name="chevron" :class="{ rotated: expanded[project.id] }" /></button>
        </div>
        <div v-if="expanded[project.id]" :id="`project-${project.id}`" class="project-children">
          <p v-if="chat.projectLoading[project.id]" class="hint" role="status">正在加载会话…</p>
          <div v-else-if="chat.projectErrors[project.id]" class="project-error"><p class="error">{{ chat.projectErrors[project.id] }}</p><button type="button" @click="load(project.id)">重试</button></div>
          <template v-else>
            <ul class="session-list">
              <li v-for="item in chat.sessionGroups[project.id]?.active ?? []" :key="item.id" :class="{ active: inChat && project.id === chat.workspaceId && item.id === chat.sessionId }">
                <a class="session-open" :href="chatHref(project.id, item.id)" :title="item.title" :aria-current="inChat && item.id === chat.sessionId && project.id === chat.workspaceId ? 'page' : undefined" @click.prevent="emit('open', chatHref(project.id, item.id))">{{ item.title }}</a>
                <span class="session-actions"><button type="button" class="icon" title="归档会话" :disabled="chat.busy" @click="emit('archive', item.id, true, project.id)">归档</button><button type="button" class="icon danger" title="删除会话" :disabled="chat.busy" @click="emit('delete', item.id, project.id)">删除</button></span>
              </li>
            </ul>
            <p v-if="!chat.sessionGroups[project.id]?.active.length" class="hint">暂无对话，从项目旁新建会话。</p>
            <div v-if="chat.sessionGroups[project.id]?.archived.length" class="archived">
              <button type="button" class="archived-toggle" :aria-expanded="!!archived[project.id]" @click="archived[project.id] = !archived[project.id]">{{ archived[project.id] ? '▾' : '▸' }} 已归档 · {{ chat.sessionGroups[project.id]?.archived.length }}</button>
              <ul v-if="archived[project.id]" class="session-list">
                <li v-for="item in chat.sessionGroups[project.id]?.archived ?? []" :key="item.id" :class="{ active: inChat && project.id === chat.workspaceId && item.id === chat.sessionId }">
                  <a class="session-open" :href="chatHref(project.id, item.id)" :title="item.title" @click.prevent="emit('open', chatHref(project.id, item.id))">{{ item.title }}</a>
                  <span class="session-actions"><button type="button" class="icon" title="恢复会话" :disabled="chat.busy" @click="emit('archive', item.id, false, project.id)">恢复</button><button type="button" class="icon danger" title="删除会话" :disabled="chat.busy" @click="emit('delete', item.id, project.id)">删除</button></span>
                </li>
              </ul>
            </div>
          </template>
        </div>
      </li>
    </ul>
  </section>
</template>
