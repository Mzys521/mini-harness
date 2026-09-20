<script setup lang="ts">
import { computed, ref } from "vue";

import IconBase from "@/components/common/IconBase.vue";
import PaneToggle from "@/components/common/PaneToggle.vue";
import SplitterBar from "@/components/common/SplitterBar.vue";
import ActivityPanel from "@/components/inspector/ActivityPanel.vue";
import ContextPanel from "@/components/inspector/ContextPanel.vue";
import ToolsPanel from "@/components/inspector/ToolsPanel.vue";
import { projectFiles } from "@/data/catalog";
import { CONTEXT_LIMITS, DEFAULT_LAYOUT, useInspectorStore } from "@/stores/inspector";
import type { ContextTab } from "@/types/domain";

const layout = useInspectorStore();

const element = ref<HTMLElement | null>(null);

/**
 * The splitter works in percentages of the column height so its aria range is
 * meaningful, while the store keeps the durable ratio (0–1).
 */
const contextPercent = computed({
  get: () => Math.round(layout.contextRatio * 100),
  set: (percent: number) => {
    layout.contextRatio = Math.min(
      Math.max(percent / 100, CONTEXT_LIMITS.min),
      CONTEXT_LIMITS.max,
    );
  },
});

const tabs: { key: ContextTab; label: string; count?: number }[] = [
  { key: "context", label: "上下文", count: projectFiles.length },
  { key: "tools", label: "工具" },
];

function onTabKeydown(event: KeyboardEvent): void {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const next: ContextTab =
    event.key === "Home"
      ? "context"
      : event.key === "End"
        ? "tools"
        : layout.tab === "context"
          ? "tools"
          : "context";
  layout.setTab(next);
  document.querySelector<HTMLElement>(`[data-tab="${next}"]`)?.focus();
}
</script>

<template>
  <aside ref="element" class="inspector" aria-label="工作空间详情">
    <section class="context-pane pane" :class="{ 'is-collapsed': layout.contextFolded }">
      <button
        v-if="layout.contextFolded"
        class="pane-rail"
        type="button"
        aria-expanded="false"
        aria-controls="context-content"
        aria-label="展开上下文与工具"
        title="展开上下文与工具"
        @click="layout.toggleContext()"
      >
        <span class="pane-rail-icon"><IconBase name="layers" /></span>
        <span class="pane-rail-title">上下文 · 工具</span>
        <span class="pane-rail-toggle" aria-hidden="true"><IconBase name="panel-bottom-expand" /></span>
      </button>

      <template v-else>
        <header class="pane-header">
          <div class="tabs" role="tablist" aria-label="工作空间详情" @keydown="onTabKeydown">
            <button
              v-for="item in tabs"
              :id="`${item.key}-tab`"
              :key="item.key"
              class="tab"
              :class="{ active: layout.tab === item.key }"
              type="button"
              role="tab"
              :aria-selected="layout.tab === item.key"
              :aria-controls="`${item.key}-content`"
              :tabindex="layout.tab === item.key ? 0 : -1"
              :data-tab="item.key"
              @click="layout.setTab(item.key)"
            >
              {{ item.label }}
              <span v-if="item.count" class="tab-count">{{ item.count }}</span>
            </button>
          </div>
          <div class="header-actions">
            <span class="header-kicker">WORKSPACE</span>
            <PaneToggle
              :collapsed="false"
              controls="context-content"
              axis="horizontal"
              label="上下文与工具"
              @toggle="layout.toggleContext()"
            />
          </div>
        </header>

        <ContextPanel v-show="layout.tab === 'context'" />
        <ToolsPanel v-show="layout.tab === 'tools'" />
      </template>
    </section>

    <SplitterBar
      v-if="!layout.contextFolded && !layout.activityFolded"
      v-model="contextPercent"
      orientation="horizontal"
      label="调整上下文与运行记录高度"
      controls="context-pane activity-pane"
      :min="CONTEXT_LIMITS.min * 100"
      :max="CONTEXT_LIMITS.max * 100"
      :step="2"
      :big-step="6"
      @reset="layout.contextRatio = DEFAULT_LAYOUT.context"
    />

    <ActivityPanel
      :collapsed="layout.activityFolded"
      @expand="layout.toggleActivity()"
      @collapse="layout.toggleActivity()"
    />
  </aside>
</template>
