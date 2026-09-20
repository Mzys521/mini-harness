<script setup lang="ts">
import { computed } from "vue";

import IconBase from "@/components/common/IconBase.vue";
import PaneToggle from "@/components/common/PaneToggle.vue";
import { useRunStore } from "@/stores/run";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";
import { shortTime } from "@/utils/format";

const workspace = useWorkspaceStore();
const run = useRunStore();
const toasts = useToastStore();

const props = defineProps<{ collapsed: boolean }>();
const emit = defineEmits<{ expand: []; collapse: [] }>();

const task = computed(() => workspace.activeTask);
const events = computed(() => task.value?.events ?? []);

function clearEvents(): void {
  if (!task.value) return;
  workspace.clearEvents(task.value);
  toasts.push("当前窗口的运行记录已清空");
}
</script>

<template>
  <section
    class="activity-pane pane"
    :class="{ 'is-collapsed': props.collapsed }"
    aria-label="运行记录"
  >
    <button
      v-if="collapsed"
      class="pane-rail"
      type="button"
      aria-expanded="false"
      aria-controls="activity-content"
      aria-label="展开运行记录"
      title="展开运行记录"
      @click="emit('expand')"
    >
      <span class="pane-rail-icon"><IconBase name="activity" /></span>
      <span class="pane-rail-title">运行记录</span>
      <span v-if="events.length" class="pane-rail-count">{{ events.length }}</span>
      <span class="pane-rail-toggle" aria-hidden="true"><IconBase name="panel-bottom-expand" /></span>
    </button>

    <template v-else>
      <header class="pane-header">
        <div class="activity-heading">
          <IconBase name="activity" />
          <strong>运行记录</strong>
          <span class="tiny-dot green" />
        </div>
        <div class="header-actions">
          <button
            class="icon-button small"
            type="button"
            aria-label="清空当前运行记录"
            title="清空记录"
            @click="clearEvents"
          >
            <IconBase name="list-clear" />
          </button>
          <PaneToggle
            :collapsed="false"
            controls="activity-content"
            axis="horizontal"
            label="运行记录"
            @toggle="emit('collapse')"
          />
        </div>
      </header>

      <div id="activity-content" class="activity-content" aria-live="polite">
        <template v-if="events.length">
          <div v-for="event in events" :key="event.id" class="event" :class="{ error: event.error }">
            <span class="event-icon">
              <IconBase :name="event.error ? 'x' : event.icon || 'check'" />
            </span>
            <div>
              <div class="event-title">{{ event.title }}</div>
              <div v-if="event.detail" class="event-detail">{{ event.detail }}</div>
            </div>
            <time :datetime="event.time">{{ shortTime(event.time) }}</time>
          </div>
        </template>
        <template v-else>
          <div class="activity-empty">
            <span class="activity-empty-icon"><IconBase name="check" /></span>
            <div>
              <strong>工作空间已就绪</strong>
              <p>发送一个任务，在这里跟随 Agent 的每一步。</p>
            </div>
          </div>
          <div class="pending-steps">
            <span><i />接收任务</span>
            <span class="step-line" />
            <span><i />工具执行</span>
            <span class="step-line" />
            <span><i />返回结果</span>
          </div>
        </template>
      </div>

      <div class="activity-footer">
        <IconBase name="shield" />
        <span>每一步，都有迹可循</span>
      </div>
    </template>
  </section>
</template>
