<script setup lang="ts">
import { computed } from "vue";

import IconBase from "@/components/common/IconBase.vue";
import MarkdownBlock from "@/components/conversation/MarkdownBlock.vue";
import { promptTemplates, type PromptKey } from "@/data/catalog";
import { useRunStore } from "@/stores/run";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";
import type { Task } from "@/types/domain";
import { shortTime } from "@/utils/format";

const workspace = useWorkspaceStore();
const run = useRunStore();
const toasts = useToastStore();

const emit = defineEmits<{
  prompt: [value: string];
  attach: [];
}>();

const task = computed<Task | undefined>(() => workspace.activeTask);
const messages = computed(() => task.value?.messages ?? []);
const showWelcome = computed(() => messages.value.length === 0);
const thinking = computed(() => {
  const current = task.value;
  if (!current) return false;
  return run.isRunning(current.id) && current.status !== "waiting";
});

const promptCards: { key: PromptKey; icon: string; title: string; caption: string }[] = [
  { key: "architecture", icon: "layers", title: "从理解项目开始", caption: "探索架构与执行流程" },
  { key: "knowledge", icon: "book", title: "让知识有迹可循", caption: "检索知识，找到可靠答案" },
  { key: "tools", icon: "terminal", title: "试试工具的力量", caption: "从一次简单计算开始" },
  { key: "note", icon: "compose", title: "留住一个好想法", caption: "体验笔记与人工审批" },
];

function usePrompt(key: PromptKey): void {
  emit("prompt", promptTemplates[key]);
}

async function copyMessage(index: number): Promise<void> {
  const content = messages.value[index]?.content;
  if (!content) return;
  try {
    await navigator.clipboard.writeText(content);
    toasts.push("回答已复制");
  } catch {
    toasts.push("浏览器未允许剪贴板访问，请选中文字复制。");
  }
}

function authorName(role: string): string {
  return role === "user" ? "你" : "Harness";
}
</script>

<template>
  <div class="conversation-scroll">
    <div v-if="showWelcome" class="welcome">
      <div class="welcome-symbol" aria-hidden="true">
        <IconBase name="harness" />
        <span class="symbol-spark" />
      </div>
      <div class="eyebrow">A LITTLE HARNESS. ENDLESS POSSIBILITIES.</div>
      <h1>让想法，<span>开始运行。</span></h1>
      <p class="welcome-description">
        一个想法，一段对话。<br>让 Agent 帮你连接知识、调用工具，把事情向前推进。
      </p>
      <div class="prompt-grid">
        <button
          v-for="card in promptCards"
          :key="card.key"
          class="prompt-card"
          type="button"
          @click="usePrompt(card.key)"
        >
          <span class="prompt-icon"><IconBase :name="card.icon" /></span>
          <strong>{{ card.title }}</strong>
          <span>{{ card.caption }}</span>
          <span class="prompt-arrow"><IconBase name="arrow-up-right" /></span>
        </button>
      </div>
      <div class="welcome-foot">
        <span class="shortcut-symbol">⌘</span>
        <span>少一点切换，多一点心流。</span>
      </div>
    </div>

    <div v-else class="messages" role="log" aria-label="对话消息" aria-live="polite" aria-relevant="additions text">
      <article
        v-for="(message, index) in messages"
        :key="index"
        class="message"
        :class="[message.role, { error: message.error }]"
      >
        <div class="message-heading">
          <span class="message-avatar">
            <IconBase :name="message.role === 'user' ? 'chat' : 'harness'" />
          </span>
          <strong>{{ authorName(message.role) }}</strong>
          <time :datetime="message.time">{{ shortTime(message.time) }}</time>
        </div>
        <div class="message-content">
          <MarkdownBlock :content="message.content" />
        </div>
        <div v-if="message.role === 'assistant'" class="message-meta">
          <button type="button" aria-label="复制这条回答" @click="copyMessage(index)">
            <IconBase name="copy" />
            <span>复制</span>
          </button>
          <span v-if="message.error">未能完成</span>
        </div>
      </article>

      <div v-if="thinking" class="thinking"><span class="spinner" />Harness 正在思考…</div>
    </div>
  </div>
</template>
