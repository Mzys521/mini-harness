<script setup lang="ts">
import { computed, ref, watch } from "vue";

import AppDialog from "@/components/common/AppDialog.vue";
import IconBase from "@/components/common/IconBase.vue";
import { useConnectionStore } from "@/stores/connection";
import { useRunStore } from "@/stores/run";
import { useToastStore } from "@/stores/toast";
import { useUiStore } from "@/stores/ui";

const connection = useConnectionStore();
const run = useRunStore();
const ui = useUiStore();
const toasts = useToastStore();

const apiKey = ref("");

const statusLabel = computed(() => {
  switch (connection.serverStatus) {
    case "online":
      return "服务在线";
    case "standalone":
      return "独立演示";
    case "offline":
      return "服务未连接";
    default:
      return "检查中";
  }
});

const origin = window.location.origin;

watch(
  () => ui.settingsOpen,
  (open) => {
    if (!open) return;
    connection.error = "";
    void connection.probeServer();
  },
);

function onClose(): void {
  apiKey.value = "";
}

function blocked(): boolean {
  if (!run.hasRunningRuns) return false;
  toasts.push("请先完成或取消正在执行的任务，再切换连接。");
  return true;
}

async function submit(): Promise<void> {
  if (blocked()) return;
  const key = apiKey.value.trim();
  if (!key) return;
  const ok = await connection.connect(key);
  if (!ok) return;
  apiKey.value = "";
  ui.closeAll();
}

function useDemo(): void {
  if (blocked()) return;
  connection.switchToDemo();
  ui.closeAll();
}
</script>

<template>
  <AppDialog
    v-model:open="ui.settingsOpen"
    class-name="settings-dialog"
    label-id="settings-title"
    @close="onClose"
  >
    <div class="dialog-top">
      <span class="dialog-icon"><IconBase name="plug" /></span>
      <button class="icon-button" type="button" aria-label="关闭连接设置" @click="ui.closeAll()">
        <IconBase name="x" />
      </button>
    </div>

    <h2 id="settings-title">{{ connection.isLive ? "Harness 已连接" : "连接你的 Harness" }}</h2>
    <p class="dialog-description">
      {{
        connection.isLive
          ? "当前会话正在使用服务端解析的租户身份。"
          : "把这个工作空间连接到正在运行的服务，让每一次对话，都成为一次真实执行。"
      }}
    </p>

    <div class="server-address">
      <span class="tiny-dot" :class="{ green: connection.serverStatus === 'online' }" />
      <span class="server-address-value">{{ origin }}</span>
      <span class="server-status">{{ statusLabel }}</span>
    </div>

    <template v-if="!connection.isLive">
      <form @submit.prevent="submit">
        <label class="field-label" for="api-key">平台 API Key</label>
        <div class="key-input-wrap">
          <IconBase name="key" />
          <input
            id="api-key"
            v-model="apiKey"
            type="password"
            placeholder="粘贴你的平台 API Key"
            autocomplete="off"
            spellcheck="false"
            required
          >
        </div>
        <p class="field-help">密钥仅保存在当前页面内存中，刷新后需要重新连接。</p>
        <p v-if="connection.error" class="form-error" role="alert">{{ connection.error }}</p>
        <button class="primary-button" type="submit" :disabled="connection.busy">
          <IconBase name="plug" />{{ connection.busy ? "正在连接…" : "连接工作空间" }}
        </button>
      </form>
      <button class="secondary-button" type="button" @click="useDemo">
        继续体验演示模式<IconBase name="arrow-right" />
      </button>
    </template>

    <button v-else class="secondary-button" type="button" @click="useDemo">
      断开并回到演示模式<IconBase name="arrow-right" />
    </button>

    <div class="setup-help">
      <span>启动服务</span><code>python main.py api</code>
      <p>先运行 platform-init 获取平台密钥，再通过服务首页连接。</p>
    </div>
  </AppDialog>
</template>
