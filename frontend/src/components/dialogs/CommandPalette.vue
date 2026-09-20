<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import AppDialog from "@/components/common/AppDialog.vue";
import IconBase from "@/components/common/IconBase.vue";
import { projectFiles } from "@/data/catalog";
import { exportConversationAsMarkdown } from "@/composables/useShortcuts";
import { useConnectionStore } from "@/stores/connection";
import { useInspectorStore } from "@/stores/inspector";
import { useToastStore } from "@/stores/toast";
import { useUiStore } from "@/stores/ui";
import { useWorkspaceStore } from "@/stores/workspace";
import type { Task } from "@/types/domain";

interface Command {
  id: string;
  label: string;
  hint: string;
  icon: string;
  run: () => void;
}

const workspace = useWorkspaceStore();
const connection = useConnectionStore();
const layout = useInspectorStore();
const ui = useUiStore();
const toasts = useToastStore();

const query = ref("");
const highlighted = ref(0);
const resultsElement = ref<HTMLElement | null>(null);

const visibleTasks = computed<Task[]>(() =>
  workspace.tasks.filter(
    (task) =>
      task.mode === connection.mode &&
      (task.mode === "demo" || task.tenantId === connection.principal?.tenant_id),
  ),
);

function newTask(): void {
  const existing = visibleTasks.value.find((task) => !task.messages.length && !task.draft);
  if (existing) workspace.selectTask(existing.id);
  else workspace.createTask(connection.mode, connection.principal?.tenant_id ?? null);
  layout.setMobileView("chat");
}

function toggleCurrentFile(): void {
  const task = workspace.activeTask;
  if (!task) return;
  const added = workspace.toggleAttachment(task, workspace.selectedFile);
  toasts.push(added ? "已添加到下一条消息的上下文" : "已移除上下文");
}

const allCommands = computed<Command[]>(() => [
  { id: "new", label: "新建任务", hint: "Ctrl N", icon: "compose", run: newTask },
  {
    id: "connect",
    label: connection.isLive ? "切换连接 / 查看身份" : "连接 Harness 服务",
    hint: "设置",
    icon: "plug",
    run: () => ui.toggle("settings"),
  },
  {
    id: "theme",
    label: layout.theme === "dark" ? "切换为浅色主题" : "切换为深色主题",
    hint: "外观",
    icon: layout.theme === "dark" ? "sun" : "moon",
    run: () => layout.toggleTheme(),
  },
  {
    id: "layout-reset",
    label: "恢复默认窗口布局",
    hint: "布局",
    icon: "grid",
    run: () => {
      layout.resetLayout();
      toasts.push("窗口布局已还原");
    },
  },
  {
    id: "fold-context",
    label: layout.contextFolded ? "展开上下文与工具" : "折叠上下文与工具",
    hint: "Ctrl B",
    icon: "layers",
    run: () => layout.toggleContext(),
  },
  {
    id: "fold-activity",
    label: layout.activityFolded ? "展开运行记录" : "折叠运行记录",
    hint: "Ctrl J",
    icon: "activity",
    run: () => layout.toggleActivity(),
  },
  {
    id: "export",
    label: "导出当前对话为 Markdown",
    hint: "导出",
    icon: "download",
    run: () => exportConversationAsMarkdown(),
  },
  {
    id: "attach-current",
    label: `将 ${workspace.selectedFile} 添加到上下文`,
    hint: "上下文",
    icon: "plus",
    run: toggleCurrentFile,
  },
  ...visibleTasks.value.map((task) => ({
    id: `task:${task.id}`,
    label: task.title === "新任务" ? "新的想法" : task.title,
    hint: "任务",
    icon: "chat",
    run: () => workspace.selectTask(task.id),
  })),
  ...projectFiles.map((file) => ({
    id: `file:${file.name}`,
    label: file.name,
    hint: "项目快照",
    icon: "file",
    run: () => {
      workspace.selectedFile = file.name;
      layout.setTab("context");
      layout.setMobileView("context");
    },
  })),
]);

const filtered = computed(() => {
  const needle = query.value.trim().toLowerCase();
  if (!needle) return allCommands.value;
  return allCommands.value.filter((command) =>
    `${command.label} ${command.hint}`.toLowerCase().includes(needle),
  );
});

watch(filtered, () => {
  highlighted.value = 0;
});

watch(
  () => ui.commandOpen,
  async (open) => {
    if (!open) return;
    query.value = "";
    highlighted.value = 0;
    await nextTick();
    resultsElement.value?.scrollTo({ top: 0 });
  },
);

function move(delta: number): void {
  const count = filtered.value.length;
  if (!count) return;
  highlighted.value = (highlighted.value + delta + count) % count;
  void nextTick(() => {
    resultsElement.value
      ?.querySelector<HTMLElement>(".command-item.highlighted")
      ?.scrollIntoView({ block: "nearest" });
  });
}

function choose(index: number): void {
  const command = filtered.value[index];
  if (!command) return;
  ui.closeAll();
  command.run();
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "ArrowDown") {
    event.preventDefault();
    move(1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    move(-1);
  } else if (event.key === "Enter") {
    event.preventDefault();
    choose(highlighted.value);
  }
}
</script>

<template>
  <AppDialog
    v-model:open="ui.commandOpen"
    class-name="command-dialog"
    label-id="command-title"
    initial-focus="#command-input"
  >
    <div class="command-search">
      <IconBase name="search" />
      <label class="sr-only" id="command-title" for="command-input">搜索任务、文件或命令</label>
      <input
        id="command-input"
        v-model="query"
        placeholder="搜索任务、文件或命令…"
        autocomplete="off"
        @keydown="onKeydown"
      >
      <button class="escape-key" type="button" aria-label="关闭搜索" @click="ui.closeAll()">Esc</button>
    </div>

    <div ref="resultsElement" class="command-results">
      <button
        v-for="(command, index) in filtered"
        :key="command.id"
        class="command-item"
        :class="{ highlighted: index === highlighted }"
        type="button"
        @click="choose(index)"
        @mousemove="highlighted = index"
      >
        <IconBase :name="command.icon" />
        <span>{{ command.label }}</span>
        <span>{{ command.hint }}</span>
      </button>
      <div v-if="!filtered.length" class="command-empty">没有找到匹配的任务或命令</div>
    </div>

    <div class="command-footer">
      <span>↑ ↓ 选择 <span>↵ 打开</span></span>
      <span>你的工作，触手可及</span>
    </div>
  </AppDialog>
</template>
