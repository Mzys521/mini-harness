import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { ApiError, api } from "@/api/client";
import { demoAnswer, projectFiles, statusLabels, terminalStatuses } from "@/data/catalog";
import { useConnectionStore } from "@/stores/connection";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";
import type { RunState, Task, TaskStatus } from "@/types/domain";

/** Non-reactive per-run control state: AbortControllers must not be proxied. */
interface RunControl {
  controller: AbortController;
  cancelRequested: boolean;
  approving: boolean;
}

const MAX_INPUT_CHARS = 16_000;
const POLL_INTERVAL_MS = 1_000;
const POLL_INTERVAL_WAITING_MS = 2_000;
const MAX_POLL_FAILURES = 3;

function abortError(): DOMException {
  return new DOMException("Cancelled", "AbortError");
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(abortError());
      return;
    }
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort(): void {
      window.clearTimeout(timer);
      reject(abortError());
    }
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * Owns the lifecycle of a run: submit, status polling, approval, cancellation
 * and recovery after a reload. Components only read the resulting task state,
 * so no run logic leaks into the view layer.
 */
export const useRunStore = defineStore("run", () => {
  const workspace = useWorkspaceStore();
  const connection = useConnectionStore();
  const toasts = useToastStore();

  const controls = new Map<string, RunControl>();
  const runningIds = ref<string[]>([]);

  const hasRunningRuns = computed(() => runningIds.value.length > 0);
  const hasLiveRuns = computed(() =>
    runningIds.value.some((id) => workspace.tasks.find((task) => task.id === id)?.mode === "live"),
  );

  function isRunning(taskId: string): boolean {
    return controls.has(taskId);
  }

  function markRunning(taskId: string): void {
    if (!runningIds.value.includes(taskId)) runningIds.value = [...runningIds.value, taskId];
  }

  function unmarkRunning(taskId: string): void {
    runningIds.value = runningIds.value.filter((id) => id !== taskId);
  }

  function begin(task: Task): RunControl {
    const control: RunControl = {
      controller: new AbortController(),
      cancelRequested: false,
      approving: false,
    };
    controls.set(task.id, control);
    markRunning(task.id);
    return control;
  }

  function end(task: Task): void {
    controls.delete(task.id);
    unmarkRunning(task.id);
  }

  function finish(
    task: Task,
    output: string,
    status: TaskStatus,
    error = false,
  ): void {
    end(task);
    task.status = status;
    task.runId = null;
    task.waitingTool = null;
    if (output) workspace.pushReply(task, output, error);
    workspace.pushEvent(
      task,
      statusLabels[status] ?? status,
      task.mode === "demo" ? "本地演示" : "Harness 服务返回",
      status === "cancelled" ? "stop" : "check",
      error,
    );
    workspace.persist();
  }

  function handleRunError(task: Task, cause: unknown): void {
    if (cause instanceof DOMException && cause.name === "AbortError") return;
    if (cause instanceof Error && cause.name === "AbortError") return;
    end(task);
    task.status = "interrupted";
    const message = cause instanceof Error ? cause.message : String(cause);
    workspace.pushReply(task, message, true);
    workspace.pushEvent(
      task,
      "连接中断",
      task.runId ? "运行仍在服务端，可恢复状态查询。" : "任务未能确认提交。请检查连接与服务端记录。",
      "info",
      true,
    );
    workspace.persist();
  }

  /** Standard responses for one poll result; shared by polling and recovery. */
  function applyTerminal(task: Task, state: RunState): boolean {
    if (!terminalStatuses.has(state.status)) return false;
    const output =
      state.output ||
      state.error_message ||
      (state.status === "cancelled" ? "运行已由服务端取消。" : "服务端未返回文本结果。");
    finish(task, output, state.status, state.status === "failed");
    return true;
  }

  function noteStatusChange(task: Task, state: RunState, previous: TaskStatus | ""): TaskStatus {
    if (state.status !== previous) {
      workspace.pushEvent(
        task,
        statusLabels[state.status] ?? "运行状态已更新",
        state.waiting_tool_name ?? task.runId ?? "",
        state.status === "waiting" ? "shield" : "activity",
      );
    }
    return state.status;
  }

  async function poll(task: Task, control: RunControl, previous: TaskStatus | "" = ""): Promise<void> {
    let failures = 0;
    let last = previous;
    while (controls.get(task.id) === control) {
      let state: RunState;
      try {
        state = await api.runState(task.runId!);
        failures = 0;
      } catch (cause) {
        failures += 1;
        if (failures >= MAX_POLL_FAILURES) throw cause;
        await pause(failures * 1_000, control.controller.signal);
        continue;
      }
      task.status = state.status;
      task.waitingTool = state.waiting_tool_name ?? null;
      if (applyTerminal(task, state)) return;
      last = noteStatusChange(task, state, last);
      workspace.persist();
      await pause(
        state.status === "waiting" ? POLL_INTERVAL_WAITING_MS : POLL_INTERVAL_MS,
        control.controller.signal,
      );
    }
  }

  async function runDemo(task: Task, input: string, control: RunControl): Promise<void> {
    const signal = control.controller.signal;
    await pause(550, signal);
    workspace.pushEvent(task, "组织演示上下文", "项目说明与已选择的快照", "layers");
    await pause(700, signal);
    if (/笔记|记录一个|记下/.test(input)) {
      task.status = "waiting";
      task.waitingTool = "create_note";
      workspace.pushEvent(task, "模拟审批暂停", "create_note · 等待你的选择", "shield");
      return;
    }
    workspace.pushEvent(task, "展示执行流程", "演示模式 · 没有调用真实工具", "terminal");
    await pause(650, signal);
    finish(task, demoAnswer(input), "completed");
  }

  async function submit(input: string): Promise<void> {
    const task = workspace.activeTask;
    if (!task) return;
    if (controls.has(task.id)) {
      await cancel(task);
      return;
    }
    if (task.runId) {
      toasts.push("请先恢复或取消当前运行。");
      return;
    }

    const trimmed = input.trim();
    if (!trimmed) return;

    const attached = task.attachments
      .map((name) => projectFiles.find((file) => file.name === name))
      .filter((file): file is (typeof projectFiles)[number] => Boolean(file));
    const fullInput =
      trimmed +
      (attached.length
        ? "\n\n用户附带的项目快照（静态摘录，仅供参考）：\n" +
          attached.map((file) => `\n--- ${file.name} ---\n${file.text}`).join("\n")
        : "");

    if ([...fullInput].length > MAX_INPUT_CHARS) {
      toasts.push("消息和上下文合计不能超过 16,000 个字符，请缩短后重试。");
      return;
    }

    if (!task.messages.length) {
      task.title = trimmed.length > 19 ? `${trimmed.slice(0, 19)}…` : trimmed;
    }
    task.messages.push({ role: "user", content: trimmed, time: new Date().toISOString() });
    task.draft = "";
    task.attachments = [];
    task.status = "pending";
    task.events = [];
    const control = begin(task);
    workspace.pushEvent(
      task,
      task.mode === "demo" ? "开始演示" : "正在提交任务",
      task.mode === "demo" ? "不消耗模型用量，不写入真实数据" : "等待服务端接收",
      "chat",
    );

    try {
      if (task.mode === "demo") {
        await runDemo(task, trimmed, control);
        return;
      }

      const submission = await api.submitRun({
        input: fullInput,
        ...(task.conversationId ? { conversation_id: task.conversationId } : {}),
      });
      if (typeof submission.run_id !== "string") {
        throw new ApiError("服务端未返回有效运行编号，请检查服务端记录。");
      }
      task.runId = submission.run_id;
      task.conversationId = submission.conversation_id;
      workspace.persist();

      const early: RunState = {
        status: submission.status,
        output: submission.output,
        error_message: submission.error_message,
        waiting_tool_name: submission.waiting_tool_name,
      };
      if (applyTerminal(task, early)) return;
      if (control.cancelRequested) await api.cancelRun(task.runId);
      await poll(task, control, noteStatusChange(task, early, ""));
    } catch (cause) {
      handleRunError(task, cause);
    }
  }

  async function cancel(task: Task | undefined = workspace.activeTask): Promise<void> {
    if (!task) return;
    const control = controls.get(task.id);

    if (task.mode === "demo") {
      control?.controller.abort();
      finish(task, "演示已停止。你可以调整想法，再开始一次。", "cancelled");
      return;
    }
    if (!connection.hasScope("runs:cancel")) {
      toasts.push("当前密钥没有 runs:cancel 权限。");
      return;
    }
    if (control?.cancelRequested) {
      toasts.push("已请求取消，正在等待服务端确认。");
      return;
    }
    if (!task.runId) {
      if (control) control.cancelRequested = true;
      toasts.push("任务提交完成后会立即请求取消。");
      return;
    }
    try {
      if (control) control.cancelRequested = true;
      await api.cancelRun(task.runId);
      workspace.pushEvent(task, "已请求取消", "等待服务端确认", "stop");
      if (!control) await resume(task);
    } catch (cause) {
      if (control) control.cancelRequested = false;
      toasts.push(cause instanceof Error ? cause.message : String(cause));
    }
  }

  async function approve(): Promise<void> {
    const task = workspace.activeTask;
    if (!task) return;
    const control = controls.get(task.id);
    if (!control || task.status !== "waiting" || control.approving) return;
    control.approving = true;
    try {
      if (task.mode === "demo") {
        task.status = "running";
        workspace.pushEvent(task, "已批准演示步骤", "继续展示结果", "shield");
        await pause(650, control.controller.signal);
        finish(
          task,
          "**审批流程体验完成**\n\n你已经走过了「请求工具 → 等待审批 → 人工批准 → 继续执行」的完整交互。\n\n" +
            "演示模式没有写入笔记。连接服务后，create_note 会按照服务端的工具策略执行实际操作。",
          "completed",
        );
      } else {
        await api.approveRun(task.runId!);
        task.status = "pending";
        workspace.pushEvent(task, "审批已提交", "等待 Worker 继续执行", "shield");
      }
    } catch (cause) {
      if (!(cause instanceof Error && cause.name === "AbortError")) {
        toasts.push(cause instanceof Error ? cause.message : String(cause));
      }
    } finally {
      control.approving = false;
    }
  }

  /** Reattach to a run that survived a reload; the server stays the truth. */
  async function resume(task: Task | undefined = workspace.activeTask): Promise<void> {
    if (!task || !task.runId || controls.has(task.id) || !connection.isLive) return;
    const control = begin(task);
    workspace.pushEvent(task, "恢复状态查询", task.runId, "activity");
    try {
      const state = await api.runState(task.runId);
      task.status = state.status;
      task.waitingTool = state.waiting_tool_name ?? null;
      if (applyTerminal(task, state)) return;
      await poll(task, control, noteStatusChange(task, state, ""));
    } catch (cause) {
      handleRunError(task, cause);
    }
  }

  /**
   * On load, any task still holding a server run id is reconciled once, so a
   * reload no longer leaves a task stuck on "running" until the user notices.
   */
  async function reconcileOnLoad(): Promise<void> {
    await Promise.all(
      workspace.tasks
        .filter((task) => task.mode === "live" && task.runId && !task.messages.some((m) => m.error))
        .map((task) => resume(task)),
    );
  }

  return {
    runningIds,
    hasRunningRuns,
    hasLiveRuns,
    isRunning,
    submit,
    cancel,
    approve,
    resume,
    reconcileOnLoad,
  };
});
