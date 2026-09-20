import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { STORAGE_KEYS, readJSON, writeJSON } from "@/api/storage";
import type { ChatMessage, Mode, PersistedWorkspace, Task, TaskStatus } from "@/types/domain";

const MAX_TASKS = 30;
const MAX_EVENTS = 60;

export function newId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function nowISO(): string {
  return new Date().toISOString();
}

/** Structural validation for anything restored from browser storage. */
function isValidTask(value: unknown): value is Task {
  if (typeof value !== "object" || value === null) return false;
  const task = value as Partial<Task>;
  return (
    typeof task.id === "string" &&
    typeof task.title === "string" &&
    (task.mode === "demo" || task.mode === "live") &&
    Array.isArray(task.messages) &&
    task.messages.every(
      (message) =>
        typeof message === "object" &&
        message !== null &&
        typeof (message as ChatMessage).content === "string" &&
        ["user", "assistant"].includes((message as ChatMessage).role),
    ) &&
    Array.isArray(task.events) &&
    task.events.every((event) => typeof event?.title === "string") &&
    (task.attachments === undefined || Array.isArray(task.attachments))
  );
}

/**
 * Owns the task list, the active task and its conversation. Presentation is
 * derived from this state by components, so nothing here touches the DOM.
 */
export const useWorkspaceStore = defineStore("workspace", () => {
  const restored = readJSON<PersistedWorkspace>(STORAGE_KEYS.workspace);
  const tasks = ref<Task[]>(
    Array.isArray(restored?.tasks) ? restored.tasks.filter(isValidTask).slice(0, MAX_TASKS) : [],
  );
  const activeId = ref<string | null>(
    restored?.activeId && tasks.value.some((task) => task.id === restored.activeId)
      ? restored.activeId
      : null,
  );
  const selectedFile = ref("main.py");
  const fileTreeOpen = ref(true);

  const activeTask = computed<Task | undefined>(() =>
    tasks.value.find((task) => task.id === activeId.value),
  );

  function persist(): void {
    writeJSON(STORAGE_KEYS.workspace, { activeId: activeId.value, tasks: tasks.value.slice(0, MAX_TASKS) });
  }

  function createTask(mode: Mode, tenantId: string | null): Task {
    const task: Task = {
      id: newId(),
      title: "新任务",
      mode,
      tenantId,
      messages: [],
      events: [],
      attachments: [],
      draft: "",
      createdAt: nowISO(),
      status: "idle",
      conversationId: null,
      runId: null,
      waitingTool: null,
      eventSeq: 0,
    };
    tasks.value = [task, ...tasks.value];
    activeId.value = task.id;
    if (tasks.value.length > MAX_TASKS) {
      // Never drop a task that still has a live run attached to it.
      const index = tasks.value.findLastIndex(
        (item) => item.id !== activeId.value && !item.runId && item.status !== "running",
      );
      if (index >= 0) tasks.value.splice(index, 1);
    }
    persist();
    return task;
  }

  function selectTask(id: string): void {
    if (!tasks.value.some((task) => task.id === id)) return;
    activeId.value = id;
    persist();
  }

  function captureDraft(text: string): void {
    const task = activeTask.value;
    if (task) task.draft = text;
  }

  function pushEvent(
    task: Task,
    title: string,
    detail = "",
    icon = "check",
    error = false,
  ): void {
    task.events.push({ id: ++task.eventSeq, title, detail, icon, error, time: nowISO() });
    if (task.events.length > MAX_EVENTS) task.events.splice(0, task.events.length - MAX_EVENTS);
    persist();
  }

  function pushReply(task: Task, content: string, error = false): void {
    task.messages.push({ role: "assistant", content, error, time: nowISO() });
  }

  function setStatus(task: Task, status: TaskStatus): void {
    task.status = status;
  }

  function clearEvents(task: Task): void {
    task.events = [];
    persist();
  }

  function toggleAttachment(task: Task, name: string): boolean {
    const index = task.attachments.indexOf(name);
    if (index >= 0) task.attachments.splice(index, 1);
    else task.attachments.push(name);
    persist();
    return index < 0;
  }

  return {
    tasks,
    activeId,
    selectedFile,
    fileTreeOpen,
    activeTask,
    persist,
    createTask,
    selectTask,
    captureDraft,
    pushEvent,
    pushReply,
    setStatus,
    clearEvents,
    toggleAttachment,
  };
});
