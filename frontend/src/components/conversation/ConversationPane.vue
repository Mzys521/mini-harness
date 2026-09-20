<script setup lang="ts">
import { computed } from "vue";

import IconBase from "@/components/common/IconBase.vue";
import ApprovalPanel from "@/components/conversation/ApprovalPanel.vue";
import MessageList from "@/components/conversation/MessageList.vue";
import { projectFiles } from "@/data/catalog";
import { useConnectionStore } from "@/stores/connection";
import { useInspectorStore } from "@/stores/inspector";
import { useRunStore } from "@/stores/run";
import { useWorkspaceStore } from "@/stores/workspace";

const workspace = useWorkspaceStore();
const connection = useConnectionStore();
const run = useRunStore();
const layout = useInspectorStore();

const emit = defineEmits<{
  attach: [];
  export: [];
}>();

const task = computed(() => workspace.activeTask);
const input = defineModel<string>("draft", { required: true });

const busy = computed(() => (task.value ? run.isRunning(task.value.id) : false));
const waiting = computed(() => task.value?.status === "waiting" && busy.value);
const pendingRun = computed(() => task.value?.mode === "live" && Boolean(task.value?.runId));
const canSubmit = computed(() => {
  if (busy.value) return !waiting.value;
  if (pendingRun.value) return false;
  return input.value.trim().length > 0;
});

const readyLabel = computed(() => {
  if (busy.value) return waiting.value ? "等待审批" : "运行中";
  return pendingRun.value ? "待恢复" : "准备就绪";
});
const inputHint = computed(() => {
  if (busy.value) return waiting.value ? "等待审批" : "正在推进";
  const length = input.value.length;
  return length ? `${length.toLocaleString()} 字符` : "随时开始";
});

const attachments = computed(() =>
  (task.value?.attachments ?? []).map(
    (name) => projectFiles.find((file) => file.name === name) ?? { name, caption: "" },
  ),
);

function onSubmit(): void {
  if (busy.value) {
    void run.cancel();
    return;
  }
  void run.submit(input.value);
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (canSubmit.value) onSubmit();
}

function resize(event: Event): void {
  const element = event.target as HTMLTextAreaElement;
  element.style.height = "auto";
  element.style.height = `${Math.min(Math.max(element.scrollHeight, 52), 180)}px`;
}

function removeAttachment(name: string): void {
  if (task.value) workspace.toggleAttachment(task.value, name);
}
</script>

<template>
  <section class="conversation pane" aria-label="Agent 对话">
    <header class="pane-header conversation-header">
      <div class="breadcrumb">
        <IconBase name="folder" />
        <span>mini-harness</span>
        <span class="crumb-separator">/</span>
        <strong>{{ task?.title ?? "新任务" }}</strong>
      </div>
      <div class="header-actions">
        <span class="mode-badge" :class="{ live: connection.isLive }">
          {{ connection.isLive ? "已连接" : "演示" }}
        </span>
        <button
          class="icon-button small"
          type="button"
          aria-label="导出当前对话"
          title="导出对话"
          @click="emit('export')"
        >
          <IconBase name="download" />
        </button>
      </div>
    </header>

    <MessageList @prompt="input = $event" @attach="emit('attach')" />

    <div class="composer-area">
      <ApprovalPanel />

      <form class="composer" @submit.prevent="onSubmit">
        <div v-if="attachments.length" class="attachments">
          <span v-for="file in attachments" :key="file.name" class="attachment-chip">
            <IconBase name="file" />
            <span>{{ file.name }}</span>
            <button type="button" :aria-label="`移除 ${file.name}`" @click="removeAttachment(file.name)">
              <IconBase name="x" />
            </button>
          </span>
        </div>

        <label class="sr-only" for="prompt-input">发送给 Harness 的任务</label>
        <textarea
          id="prompt-input"
          v-model="input"
          placeholder="描述你的想法，剩下的交给 Harness…"
          rows="2"
          maxlength="15000"
          @input="resize"
          @keydown="onKeydown"
        />

        <div class="composer-toolbar">
          <div class="composer-options">
            <button
              class="icon-button"
              type="button"
              aria-label="添加项目上下文"
              title="添加上下文"
              @click="emit('attach')"
            >
              <IconBase name="plus" />
            </button>
            <span class="toolbar-divider" />
            <button class="mode-control" type="button" @click="layout.setMobileView('context')">
              <IconBase name="sparkles" />
              <span>{{ connection.isLive ? "Harness Agent" : "演示模式" }}</span>
              <IconBase name="chevron-down" />
            </button>
          </div>
          <div class="composer-submit">
            <span class="input-hint">{{ inputHint }}</span>
            <button
              class="send-button"
              :class="{ stopping: busy }"
              type="submit"
              :aria-label="busy ? '取消当前运行' : '发送任务'"
              :disabled="!canSubmit"
            >
              <IconBase :name="busy ? 'stop' : 'arrow-up'" />
            </button>
          </div>
        </div>
      </form>

      <div class="composer-caption">
        <span><kbd>Enter</kbd> 发送 <span class="caption-dot">·</span> <kbd>Shift + Enter</kbd> 换行</span>
        <span>
          <span class="tiny-dot green" :class="{ pulse: busy }" />
          <span>{{ readyLabel }}</span>
        </span>
      </div>
    </div>
  </section>
</template>
