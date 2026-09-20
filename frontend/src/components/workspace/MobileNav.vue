<script setup lang="ts">
import IconBase from "@/components/common/IconBase.vue";
import { useInspectorStore } from "@/stores/inspector";
import type { MobileView } from "@/types/domain";

const layout = useInspectorStore();

const views: { key: MobileView; label: string; icon: string }[] = [
  { key: "tasks", label: "任务", icon: "sidebar" },
  { key: "chat", label: "对话", icon: "chat" },
  { key: "context", label: "工作空间", icon: "layers" },
];
</script>

<template>
  <nav class="mobile-nav" aria-label="窗口切换">
    <button
      v-for="view in views"
      :key="view.key"
      type="button"
      :class="{ active: layout.mobileView === view.key }"
      :aria-current="layout.mobileView === view.key ? 'page' : undefined"
      :aria-label="`切换到${view.label}`"
      @click="layout.setMobileView(view.key)"
    >
      <IconBase :name="view.icon" />
      <span>{{ view.label }}</span>
    </button>
  </nav>
</template>
