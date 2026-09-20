<script setup lang="ts">
import IconBase from "@/components/common/IconBase.vue";
import { useConnectionStore } from "@/stores/connection";
import { useInspectorStore } from "@/stores/inspector";

const connection = useConnectionStore();
const layout = useInspectorStore();

const emit = defineEmits<{
  search: [];
  settings: [];
}>();

function toggleTheme(): void {
  layout.toggleTheme();
}
</script>

<template>
  <header class="titlebar">
    <div class="brand">
      <span class="brand-mark"><IconBase name="harness" /></span>
      <span>mini-harness</span>
      <span class="titlebar-divider" />
      <span class="titlebar-label">工作台</span>
    </div>
    <div class="titlebar-center"><span class="tiny-dot" /> 本地工作空间</div>
    <div class="titlebar-actions">
      <button class="icon-button" type="button" aria-label="搜索任务与命令" title="搜索 · Ctrl K" @click="emit('search')">
        <IconBase name="search" />
      </button>
      <button
        class="icon-button"
        type="button"
        :aria-label="layout.theme === 'dark' ? '切换浅色主题' : '切换深色主题'"
        title="切换主题"
        @click="toggleTheme"
      >
        <IconBase :name="layout.theme === 'dark' ? 'sun' : 'moon'" />
      </button>
      <button class="icon-button" type="button" aria-label="连接设置" title="连接设置" @click="emit('settings')">
        <IconBase name="settings" />
      </button>
    </div>
    <span class="sr-only" aria-live="polite">{{ connection.isLive ? '已连接 Harness' : '本地演示模式' }}</span>
  </header>
</template>
