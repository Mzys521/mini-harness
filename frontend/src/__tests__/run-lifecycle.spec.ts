import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { STORAGE_KEYS } from "@/api/storage";
import { useConnectionStore } from "@/stores/connection";
import { useRunStore } from "@/stores/run";
import { useWorkspaceStore } from "@/stores/workspace";

/**
 * Demo mode exercises the whole submit path (task creation, event log, canned
 * answer, run bookkeeping) without a server, so it is the cheapest way to keep
 * the run lifecycle honest.
 */
describe("demo run lifecycle", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("drives a demo task from submit to completion", async () => {
    setActivePinia(createPinia());
    const workspace = useWorkspaceStore();
    const run = useRunStore();

    const task = workspace.createTask("demo", null);
    expect(run.isRunning(task.id)).toBe(false);

    const started = run.submit("请调用计算器工具，计算 (128 + 64) × 3。");

    // The user turn and the first event land synchronously.
    expect(task.messages).toHaveLength(1);
    expect(task.messages[0].role).toBe("user");
    expect(task.title).not.toBe("新任务");
    expect(run.isRunning(task.id)).toBe(true);
    expect(task.events[0].title).toBe("开始演示");

    await started;

    expect(run.isRunning(task.id)).toBe(false);
    expect(task.status).toBe("completed");
    expect(task.messages).toHaveLength(2);
    expect(task.messages[1].role).toBe("assistant");
    expect(task.messages[1].content).toContain("576");
    expect(task.events.at(-1)?.title).toBe("执行完成");
    // Two events are recorded mid-run, plus context and completion.
    expect(task.events.length).toBeGreaterThanOrEqual(4);
  });

  it("pauses a note request on the approval gate and resumes on approve", async () => {
    setActivePinia(createPinia());
    const workspace = useWorkspaceStore();
    const run = useRunStore();

    const task = workspace.createTask("demo", null);
    await run.submit("请创建一条笔记，先把想法写下来。");

    expect(task.status).toBe("waiting");
    expect(task.waitingTool).toBe("create_note");
    expect(run.isRunning(task.id)).toBe(true);

    await run.approve();

    expect(task.status).toBe("completed");
    expect(run.isRunning(task.id)).toBe(false);
    expect(task.messages.at(-1)?.content).toContain("审批流程体验完成");
  });

  it("cancels a running demo task", async () => {
    setActivePinia(createPinia());
    const workspace = useWorkspaceStore();
    const run = useRunStore();

    const task = workspace.createTask("demo", null);
    const started = run.submit("帮我梳理 mini-harness 的核心架构。");
    await run.cancel();
    await started;

    expect(task.status).toBe("cancelled");
    expect(run.isRunning(task.id)).toBe(false);
    expect(task.messages.at(-1)?.content).toContain("演示已停止");
  });

  it("persists the task list so a reload can restore drafts", () => {
    setActivePinia(createPinia());
    const workspace = useWorkspaceStore();
    const task = workspace.createTask("demo", null);
    task.draft = "半句话的想法";

    workspace.persist();

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEYS.workspace) ?? "{}");
    expect(stored.activeId).toBe(task.id);
    expect(stored.tasks[0].draft).toBe("半句话的想法");
  });

  it("reports an active run so the UI can block connection switching", async () => {
    setActivePinia(createPinia());
    const workspace = useWorkspaceStore();
    const connection = useConnectionStore();
    const run = useRunStore();

    workspace.createTask("demo", null);
    // Demo never exposes a server-resolved principal, so no scope is granted.
    expect(connection.hasScope("runs:create")).toBe(false);

    const started = run.submit("请调用计算器工具，计算 (128 + 64) × 3。");
    expect(run.hasRunningRuns).toBe(true);
    await started;
    expect(run.hasRunningRuns).toBe(false);
  });
});
