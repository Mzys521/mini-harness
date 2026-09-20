<script setup lang="ts">
import { computed } from "vue";

import IconBase from "@/components/common/IconBase.vue";
import { shortTime } from "@/utils/format";
import { useConnectionStore } from "@/stores/connection";
import { useRunStore } from "@/stores/run";
import { useInspectorStore } from "@/stores/inspector";
import { useWorkspaceStore } from "@/stores/workspace";
import type { Task } from "@/types/domain";

const workspace = useWorkspaceStore();
const connection = useConnectionStore();
const run = useRunStore();
const layout = useInspectorStore();

const emit = defineEmits<{
  search: [];
  newTask: [];
  settings: [];
  select: [id: string];
}>();

/**
 * Live mode only shows tasks belonging to the connected tenant, so switching
 * keys never leaks another tenant's local history into the sidebar.
 */
const visibleTasks = computed<Task[]>(() =>
  workspace.tasks.filter(
    (task) =>
      task.mode === connection.mode &&
      (task.mode === "demo" || task.tenantId === connection.principal?.tenant_id),
  ),
);

const runCount = computed(() =>
  visibleTasks.value.reduce(
    (total, task) => total + task.messages.filter((message) => message.role === "user").length,
    0,
  ),
);

function displayName(task: Task): string {
  return task.title === "新任务" ? "新的想法" : task.title;
}

function timeLabel(task: Task): string {
  return task.messages.length ? shortTime(task.createdAt) : "草稿";
}
</script>

<template>
  <aside class="sidebar" aria-label="任务导航">
    <div class="sidebar-top">
      <button class="new-task" type="button" @click="emit('newTask')">
        <IconBase name="compose" />
        <span>新建任务</span>
        <kbd>Ctrl N</kbd>
      </button>
      <button class="nav-item search-nav" type="button" @click="emit('search')">
        <IconBase name="search" />
        <span>搜索</span>
        <kbd>Ctrl K</kbd>
      </button>
    </div>

    <nav class="main-navigation" aria-label="工作区导航">
      <button class="nav-item selected" type="button" @click="layout.setMobileView('chat')">
        <IconBase name="grid" />
        <span>工作台</span>
        <span class="nav-indicator" />
      </button>
      <button class="nav-item" type="button" @click="layout.revealActivity(); layout.setMobileView('context')">
        <IconBase name="activity" />
        <span>运行记录</span>
        <span class="nav-count">{{ runCount }}</span>
      </button>
      <button class="nav-item" type="button" @click="layout.setTab('tools'); layout.setMobileView('context')">
        <IconBase name="box" />
        <span>知识与工具</span>
      </button>
    </nav>

    <div class="task-section">
      <div class="section-label">
        <span>任务</span>
        <button class="icon-button small" type="button" aria-label="添加任务" @click="emit('newTask')">
          <IconBase name="plus" />
        </button>
      </div>
      <div class="task-list">
        <p v-if="!visibleTasks.length" class="empty-tasks">还没有任务。<br>描述一个想法，就开始。</p>
        <button
          v-for="task in visibleTasks"
          :key="task.id"
          class="task-item"
          :class="{ active: task.id === workspace.activeId }"
          type="button"
          :aria-current="task.id === workspace.activeId ? 'page' : undefined"
          :title="task.title"
          @click="emit('select', task.id)"
        >
          <IconBase :name="task.messages.length ? 'chat' : 'compose'" />
          <span class="task-item-name">{{ displayName(task) }}</span>
          <span v-if="run.isRunning(task.id)" class="tiny-dot green pulse" />
          <span v-else class="task-item-time">{{ timeLabel(task) }}</span>
        </button>
      </div>
    </div>

    <div class="sidebar-bottom">
      <div class="project-switcher">
        <span class="project-avatar">mh<span /></span>
        <div>
          <strong>mini-harness</strong>
          <span>Agent 开发工作空间</span>
        </div>
        <span class="project-version">v0.11</span>
      </div>
      <button class="connection-card" type="button" @click="emit('settings')">
        <span class="connection-icon"><IconBase name="plug" /></span>
        <span>
          <strong>{{ connection.isLive ? "Harness 已连接" : "连接你的 Harness" }}</strong>
          <small>{{ connection.isLive ? connection.tenantLabel : "从一个想法，到一次真实执行" }}</small>
        </span>
        <IconBase name="arrow-up-right" />
      </button>
      <div class="sidebar-foot">
        <span>
          <span class="tiny-dot green" />
          <span>{{ connection.isLive ? "服务已连接" : "本地演示" }}</span>
        </span>
        <span class="quiet">尽管开始。</span>
      </div>
    </div>
  </aside>
</template>
