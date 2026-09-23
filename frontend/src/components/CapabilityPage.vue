<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { ApiError, request } from '@/api/client';
import { NAV_PAGES, type Page } from '@/composables/useWorkbenchRoute';
import AppIcon from './AppIcon.vue';

const props = defineProps<{ page: Page }>();
const emit = defineEmits<{ back: [] }>();
interface Server { name: string; transport: string; tools: string[] }
interface Repository { id: string; name: string; description: string; embedding_model: string }
interface KnowledgeFile { id: string; filename: string; chunk_count: number; size_bytes: number }
const meta = computed(() => NAV_PAGES.find(item => item.id === props.page));
const loading = ref(false);
const error = ref('');
const unavailable = ref(false);
const servers = ref<Server[]>([]);
const repositories = ref<Repository[]>([]);
const files = ref<Record<string, KnowledgeFile[]>>({});
const fileErrors = ref<Record<string, string>>({});
const fileLoading = ref<Record<string, boolean>>({});
const expanded = ref<Record<string, boolean>>({});
const creating = ref(false), saving = ref(false), name = ref(''), description = ref(''), mutationError = ref('');
const uploading = ref<Record<string, boolean>>({});
async function createRepository(): Promise<void> {
  saving.value = true; mutationError.value = '';
  try {
    const repo = await request<Repository>('/v1/knowledge/repositories', { method: 'POST', body: JSON.stringify({ name: name.value, description: description.value }) });
    await load(); creating.value = false; name.value = ''; description.value = ''; toggleFiles(repo.id);
  } catch (caught) { mutationError.value = (caught as Error).message; }
  finally { saving.value = false; }
}
async function upload(id: string, event: Event): Promise<void> {
  const input = event.target as HTMLInputElement, file = input.files?.[0];
  if (!file) return;
  uploading.value[id] = true; fileErrors.value[id] = '';
  try {
    await request(`/v1/knowledge/repositories/${encodeURIComponent(id)}/files?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' }, signal: AbortSignal.timeout(120000),
    });
    await loadFiles(id);
  } catch (caught) { fileErrors.value[id] = (caught as Error).message; }
  finally { uploading.value[id] = false; input.value = ''; }
}
let generation = 0;
async function load(): Promise<void> {
  const version = ++generation;
  error.value = ''; unavailable.value = false; loading.value = false;
  servers.value = []; repositories.value = []; files.value = {}; fileErrors.value = {}; fileLoading.value = {}; expanded.value = {};
  const page = props.page;
  if (page !== 'plugins' && page !== 'explore') return;
  loading.value = true;
  try {
    if (page === 'plugins') {
      const data = await request<{ items: Server[] }>('/v1/mcp/servers');
      if (version === generation) servers.value = data.items;
    } else {
      const data = await request<{ items: Repository[] }>('/v1/knowledge/repositories');
      if (version === generation) repositories.value = data.items;
    }
  } catch (caught) {
    if (version === generation) {
      unavailable.value = caught instanceof ApiError && [404, 503].includes(caught.status ?? 0);
      error.value = caught instanceof ApiError && caught.status === 404
        ? '当前服务没有提供此接口，请重启更新后的 Harness Local 服务。'
        : (caught as Error).message;
    }
  } finally { if (version === generation) loading.value = false; }
}
async function loadFiles(id: string): Promise<void> {
  const version = generation;
  fileLoading.value[id] = true; fileErrors.value[id] = '';
  try {
    const data = await request<{ items: KnowledgeFile[] }>(`/v1/knowledge/repositories/${encodeURIComponent(id)}/files`);
    if (version === generation) files.value[id] = data.items;
  } catch (caught) { if (version === generation) fileErrors.value[id] = (caught as Error).message; }
  finally { if (version === generation) fileLoading.value[id] = false; }
}
function toggleFiles(id: string): void {
  expanded.value[id] = !expanded.value[id];
  if (expanded.value[id] && !files.value[id] && !fileLoading.value[id]) void loadFiles(id);
}
watch(() => props.page, load, { immediate: true });
onUnmounted(() => { generation++; });
</script>

<template>
  <section class="route-page">
    <header class="page-heading"><div class="page-symbol"><AppIcon :name="meta?.icon ?? 'search'" /></div><div><small>MINI HARNESS</small><h1>{{ meta?.label ?? '页面不存在' }}</h1></div></header>
    <template v-if="page === 'pull-requests'">
      <div class="page-empty"><span class="capability-badge">尚未接入</span><h2>代码协作，从项目对话开始。</h2><p>当前 Harness 尚未提供 Pull Request 列表与管理服务。你可以回到项目对话，继续处理代码。</p><button type="button" @click="emit('back')">返回项目对话</button></div>
    </template>
    <template v-else-if="page === 'plugins' || page === 'explore'">
      <div class="page-intro"><p>{{ page === 'plugins' ? '查看本地 Harness 已连接的 MCP 服务与可用工具。' : '浏览 Harness 知识库及已索引的文件。' }}</p><button type="button" :disabled="loading" @click="load">刷新</button></div>
      <p v-if="loading" class="hint" role="status">正在加载…</p>
      <div v-else-if="error" class="page-empty" role="status"><h2>{{ unavailable ? '此服务暂不可用' : '加载失败' }}</h2><p>{{ error }}</p><button type="button" @click="load">重试</button></div>
      <template v-else-if="page === 'plugins'">
        <div v-if="!servers.length" class="page-empty"><h2>还没有连接的 MCP 服务</h2><p>连接服务后，可用工具会显示在这里。</p></div>
        <article v-for="server in servers" :key="server.name" class="capability-card"><header><AppIcon name="plugin" /><h2>{{ server.name }}</h2><span class="capability-badge">{{ server.transport }}</span></header><p class="hint">{{ server.tools.length }} 个工具</p><ul class="tool-tags"><li v-for="tool in server.tools" :key="tool"><code>{{ tool }}</code></li></ul></article>
      </template>
      <template v-else>
        <div class="page-toolbar"><button class="primary" :disabled="saving" @click="creating = !creating">创建知识库</button><span class="hint">上传 UTF-8 文本文件，索引完成后可在项目对话中检索。</span></div>
        <p v-if="mutationError" class="error" role="alert">{{ mutationError }}</p>
        <form v-if="creating" class="capability-card editor-form" @submit.prevent="createRepository"><h2>创建 RAG 知识库</h2><label class="field"><span>名称</span><input v-model="name" required maxlength="120" /></label><label class="field"><span>描述</span><textarea v-model="description" rows="3" maxlength="2000" /></label><footer class="page-toolbar"><button class="primary" :disabled="saving">{{ saving ? '创建中…' : '创建' }}</button><button type="button" :disabled="saving" @click="creating = false">取消</button></footer></form>
        <div v-if="!repositories.length" class="page-empty"><h2>还没有知识库</h2><p>创建知识库并索引文件后，即可在这里浏览。</p></div>
        <article v-for="repo in repositories" :key="repo.id" class="capability-card">
          <button type="button" class="repository-toggle" :aria-expanded="!!expanded[repo.id]" @click="toggleFiles(repo.id)"><AppIcon name="folder" /><strong>{{ repo.name }}</strong><AppIcon name="chevron" :class="{ rotated: expanded[repo.id] }" /></button>
          <p v-if="repo.description">{{ repo.description }}</p><p class="hint">向量模型 · <span class="mono">{{ repo.embedding_model }}</span></p>
          <div v-if="expanded[repo.id]" class="repository-files">
            <label class="file-button">{{ uploading[repo.id] ? '正在索引…' : '上传文件' }}<input type="file" :disabled="uploading[repo.id]" @change="upload(repo.id, $event)" /></label>
            <p v-if="fileLoading[repo.id]" class="hint" role="status">正在加载文件…</p>
            <div v-else-if="fileErrors[repo.id]"><p class="error">{{ fileErrors[repo.id] }}</p><button type="button" @click="loadFiles(repo.id)">重试</button></div>
            <template v-else><p v-if="!files[repo.id]?.length" class="hint">暂无已索引文件。</p><ul><li v-for="file in files[repo.id]" :key="file.id"><AppIcon name="read" /><span>{{ file.filename }}</span><small>{{ file.chunk_count }} 个片段 · {{ file.size_bytes }} B</small></li></ul></template>
          </div>
        </article>
      </template>
    </template>
    <div v-else class="page-empty"><p>这个地址没有对应页面。</p><button type="button" @click="emit('back')">返回项目对话</button></div>
  </section>
</template>
