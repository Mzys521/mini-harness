<script setup lang="ts">
import { computed } from "vue";

import { useConnectionStore } from "@/stores/connection";
import { useRunStore } from "@/stores/run";
import { useWorkspaceStore } from "@/stores/workspace";

/**
 * Surfaces the two states that need a human decision: a run paused on an
 * approval gate, and a run that survived a reload and can be re-attached.
 */
const workspace = useWorkspaceStore();
const run = useRunStore();
const connection = useConnectionStore();

const task = computed(() => workspace.activeTask);
const waiting = computed(() => {
  const current = task.value;
  return Boolean(current && current.status === "waiting" && run.isRunning(current.id));
});
const recoverable = computed(() => {
  const current = task.value;
  return Boolean(current && current.mode === "live" && current.runId && !run.isRunning(current.id));
});

const canApprove = computed(() => !connection.isLive || connection.canApprove);
const canCancel = computed(() => !connection.isLive || connection.canCancel);
</script>

<template>
  <div v-if="waiting" class="approval-panel">
    <strong>{{ task?.mode === "demo" ? "体验一次人工审批" : "此运行正在等待人工处理" }}</strong>
    <p v-if="task?.mode === 'demo'">模拟 create_note：批准后将展示示例结果，不会写入笔记。</p>
    <p v-else>
      工具：{{ task?.waitingTool || "服务端等待状态" }}。批准操作由服务端校验；需要对账的运行请在服务端处理。
    </p>
    <div class="approval-actions">
      <button type="button" :disabled="!canApprove" @click="run.approve()">批准并继续</button>
      <button type="button" :disabled="!canCancel" @click="run.cancel()">取消运行</button>
    </div>
  </div>

  <div v-else-if="recoverable" class="approval-panel">
    <strong>运行仍保留在服务端</strong>
    <p>恢复状态查询以获取最新结果，不会重复提交任务。</p>
    <div class="approval-actions">
      <button type="button" @click="run.resume()">恢复状态查询</button>
      <button type="button" @click="run.cancel()">请求取消运行</button>
    </div>
  </div>
</template>
