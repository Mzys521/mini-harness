<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { onStorageUnavailable } from "@/api/storage";
import SplitterBar from "@/components/common/SplitterBar.vue";
import ConversationPane from "@/components/conversation/ConversationPane.vue";
import AttachmentDialog from "@/components/dialogs/AttachmentDialog.vue";
import CommandPalette from "@/components/dialogs/CommandPalette.vue";
import ConnectionDialog from "@/components/dialogs/ConnectionDialog.vue";
import InspectorColumn from "@/components/inspector/InspectorColumn.vue";
import MobileNav from "@/components/workspace/MobileNav.vue";
import StatusBar from "@/components/workspace/StatusBar.vue";
import TitleBar from "@/components/workspace/TitleBar.vue";
import ToastStack from "@/components/workspace/ToastStack.vue";
import WorkspaceSidebar from "@/components/workspace/WorkspaceSidebar.vue";
import { exportConversationAsMarkdown, useShortcuts } from "@/composables/useShortcuts";
import { useConnectionStore } from "@/stores/connection";
import {
  DEFAULT_LAYOUT,
  INSPECTOR_LIMITS,
  SIDEBAR_LIMITS,
  useInspectorStore,
} from "@/stores/inspector";
import { useRunStore } from "@/stores/run";
import { useToastStore } from "@/stores/toast";
import { useUiStore } from "@/stores/ui";
import { useWorkspaceStore } from "@/stores/workspace";

const workspace = useWorkspaceStore();
const connection = useConnectionStore();
const layout = useInspectorStore();
const run = useRunStore();
const ui = useUiStore();
const toasts = useToastStore();

useShortcuts();

/** Composer text is mirrored from the active task so switching keeps drafts. */
const draft = ref(workspace.activeTask?.draft ?? "");

watch(
  () => workspace.activeId,
  () => {
    draft.value = workspace.activeTask?.draft ?? "";
  },
);
watch(
  () => workspace.activeTask?.draft,
  (value) => {
    if (value !== undefined && value !== draft.value) draft.value = value;
  },
);
watch(draft, (value) => {
  if (workspace.activeTask) workspace.activeTask.draft = value;
});

const sidebarWidth = computed({
  get: () => layout.sidebar,
  set: (value: number) => {
    layout.sidebar = Math.min(Math.max(value, SIDEBAR_LIMITS.min), SIDEBAR_LIMITS.max);
  },
});

const inspectorWidth = computed({
  get: () => layout.inspector,
  set: (value: number) => {
    layout.inspector = Math.min(Math.max(value, INSPECTOR_LIMITS.min), INSPECTOR_LIMITS.max);
  },
});

const workspaceClass = computed(() => ({
  "inspector-both-open": layout.inspectorClass === "inspector-both-open",
  "inspector-single-pane": layout.inspectorClass === "inspector-single-pane",
}));

const workspaceStyle = computed(() => ({
  "--sidebar-width": `${layout.sidebar}px`,
  "--inspector-width": layout.contextFolded ? "var(--pane-rail-width)" : `${layout.inspector}px`,
  "--context-height": `${layout.contextRatio * 100}%`,
  "--activity-height": `${(1 - layout.contextRatio) * 100}%`,
}));

function newTask(): void {
  const existing = workspace.tasks.find(
    (task) => task.mode === connection.mode && !task.messages.length && !task.draft,
  );
  if (existing) workspace.selectTask(existing.id);
  else workspace.createTask(connection.mode, connection.principal?.tenant_id ?? null);
  draft.value = "";
  layout.setMobileView("chat");
  void focusComposer();
}

async function focusComposer(): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, 0));
  document.querySelector<HTMLTextAreaElement>("#prompt-input")?.focus();
}

onStorageUnavailable(() => {
  toasts.push("浏览器存储不可用，本次内容会保留到页面关闭。");
});

onMounted(() => {
  // Theme is applied before the shell is interactive; `applyTheme` is the only
  // writer, so calling it here keeps the DOM attribute and the store in sync.
  layout.applyTheme(layout.theme);
  // Re-attach to any run that survived a reload instead of leaving it stuck.
  void run.reconcileOnLoad();
});
</script>

<template>
  <div class="app-shell">
    <TitleBar @search="ui.toggle('command')" @settings="ui.toggle('settings')" />

    <main
      class="workspace"
      :class="workspaceClass"
      :style="workspaceStyle"
      :data-mobile-view="layout.mobileView"
    >
      <WorkspaceSidebar
        @search="ui.toggle('command')"
        @new-task="newTask"
        @settings="ui.toggle('settings')"
        @select="workspace.selectTask($event)"
      />

      <SplitterBar
        v-show="!layout.isMobile"
        v-model="sidebarWidth"
        orientation="vertical"
        label="调整任务栏宽度"
        controls="sidebar"
        :min="SIDEBAR_LIMITS.min"
        :max="SIDEBAR_LIMITS.max"
        :direction="-1"
        @reset="layout.sidebar = DEFAULT_LAYOUT.sidebar"
      />

      <ConversationPane
        v-model:draft="draft"
        @attach="ui.toggle('attachment')"
        @export="exportConversationAsMarkdown()"
      />

      <SplitterBar
        v-show="!layout.isMobile && !layout.contextFolded"
        v-model="inspectorWidth"
        orientation="vertical"
        label="调整上下文窗口宽度"
        controls="inspector"
        :min="INSPECTOR_LIMITS.min"
        :max="INSPECTOR_LIMITS.max"
        :direction="-1"
        @reset="layout.inspector = DEFAULT_LAYOUT.inspector"
      />

      <InspectorColumn />
    </main>

    <MobileNav />
    <StatusBar />
  </div>

  <ToastStack />
  <CommandPalette />
  <ConnectionDialog />
  <AttachmentDialog />
</template>
