<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { request } from '@/api/client';
import { useChat, type DirectoryListing } from '@/stores/chat';

/**
 * Workspace creation. A path can be typed directly or picked from the server's
 * own directory listing (`/v1/directories`), which never exposes file contents.
 */
const emit = defineEmits<{ close: []; created: [] }>();
const chat = useChat();
const path = ref('');
const name = ref('');
const create = ref(false);
const listing = ref<DirectoryListing | null>(null);
const localError = ref('');

async function browse(target?: string): Promise<void> {
  try {
    const query = target ? `?path=${encodeURIComponent(target)}` : '';
    listing.value = await request<DirectoryListing>(`/v1/directories${query}`);
    path.value = listing.value.path;
    localError.value = '';
  } catch (caught) {
    localError.value = (caught as Error).message;
  }
}

async function submit(): Promise<void> {
  if (!path.value.trim()) return;
  await chat.createWorkspace({ path: path.value.trim(), name: name.value.trim(), create: create.value });
  if (!chat.error) { emit('created'); emit('close'); }
}

onMounted(() => void browse());
</script>

<template>
  <section class="creator">
    <header>
      <h2>新建工作区</h2>
      <button class="link" type="button" @click="emit('close')">取消</button>
    </header>

    <label class="field">
      <span>目录路径</span>
      <input v-model="path" type="text" spellcheck="false" placeholder="例如 E:\project\my-app" @keydown.enter.prevent="submit" />
    </label>
    <label class="field">
      <span>显示名称（可选）</span>
      <input v-model="name" type="text" placeholder="默认使用目录名" />
    </label>
    <label class="checkbox">
      <input v-model="create" type="checkbox" />
      <span>目录不存在时创建它</span>
    </label>

    <div v-if="listing" class="browser">
      <div class="browser-path">
        <button type="button" class="link" @click="browse(listing.parent)">↑ 上级</button>
        <span class="mono">{{ listing.path }}</span>
      </div>
      <div class="browser-roots">
        <button v-for="root in listing.roots" :key="root" type="button" class="chip" @click="browse(root)">{{ root }}</button>
      </div>
      <ul class="browser-list">
        <li v-for="directory in listing.directories" :key="directory.path">
          <button type="button" @click="browse(directory.path)">{{ directory.name }}</button>
        </li>
        <li v-if="!listing.directories.length" class="empty">没有子目录</li>
      </ul>
    </div>

    <p v-if="localError || chat.error" class="error">{{ localError || chat.error }}</p>

    <footer>
      <button class="primary" type="button" :disabled="chat.busy || !path.trim()" @click="submit">
        {{ chat.busy ? '正在保存…' : '添加工作区' }}
      </button>
    </footer>
  </section>
</template>
