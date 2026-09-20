import { onBeforeUnmount, onMounted } from "vue";

import { useConnectionStore } from "@/stores/connection";
import { useInspectorStore } from "@/stores/inspector";
import { useToastStore } from "@/stores/toast";
import { useUiStore } from "@/stores/ui";
import { useWorkspaceStore } from "@/stores/workspace";

/**
 * Global keyboard accelerators, kept out of components so no view owns
 * application-wide behaviour.
 *
 *   Ctrl/⌘ K  command palette        Ctrl/⌘ B  fold context & tools
 *   Ctrl/⌘ N  new task               Ctrl/⌘ J  fold run log
 */
export function useShortcuts(): void {
  const workspace = useWorkspaceStore();
  const connection = useConnectionStore();
  const layout = useInspectorStore();
  const ui = useUiStore();

  function newTask(): void {
    const existing = workspace.tasks.find(
      (task) => task.mode === connection.mode && !task.messages.length && !task.draft,
    );
    if (existing) workspace.selectTask(existing.id);
    else workspace.createTask(connection.mode, connection.principal?.tenant_id ?? null);
    layout.setMobileView("chat");
  }

  function onKeydown(event: KeyboardEvent): void {
    if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
    const key = event.key.toLowerCase();

    if (key === "k") {
      event.preventDefault();
      ui.toggle("command");
      return;
    }
    if (ui.anyDialogOpen) return;

    if (key === "n") {
      event.preventDefault();
      newTask();
      return;
    }
    if (key === "b") {
      event.preventDefault();
      layout.toggleContext();
      return;
    }
    if (key === "j") {
      event.preventDefault();
      layout.toggleActivity();
    }
  }

  function beforeUnload(event: BeforeUnloadEvent): void {
    const live = workspace.tasks.some((task) => task.mode === "live" && task.runId);
    if (!live) return;
    event.preventDefault();
    event.returnValue = "";
  }

  function onPageHide(): void {
    workspace.persist();
  }

  onMounted(() => {
    document.addEventListener("keydown", onKeydown);
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("pagehide", onPageHide);
  });

  onBeforeUnmount(() => {
    document.removeEventListener("keydown", onKeydown);
    window.removeEventListener("beforeunload", beforeUnload);
    window.removeEventListener("pagehide", onPageHide);
  });
}

/** Download the active conversation as Markdown. */
export function exportConversationAsMarkdown(): void {
  const workspace = useWorkspaceStore();
  const toasts = useToastStore();
  const task = workspace.activeTask;
  if (!task) return;
  if (!task.messages.length) {
    toasts.push("开始一段对话后，就可以导出记录。");
    return;
  }
  const header = `# ${task.title}\n\n${task.mode === "demo" ? "界面演示 · 未调用模型" : "Harness 对话"}\n\n`;
  const body = task.messages
    .map((message) => `## ${message.role === "user" ? "你" : "Harness"}\n\n${message.content}`)
    .join("\n\n");
  const url = URL.createObjectURL(
    new Blob([header + body], { type: "text/markdown;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `harness-${task.id.slice(0, 8)}.md`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  toasts.push("对话已导出为 Markdown");
}
