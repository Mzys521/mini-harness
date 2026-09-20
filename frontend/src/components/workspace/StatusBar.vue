<script setup lang="ts">
import IconBase from "@/components/common/IconBase.vue";
import { useConnectionStore } from "@/stores/connection";

const connection = useConnectionStore();
</script>

<template>
  <footer class="statusbar">
    <div>
      <IconBase name="branch" />
      <span>local</span>
      <span class="status-divider">/</span>
      <span>mini-harness</span>
    </div>
    <div class="status-center">一个安静、专注的工作空间。</div>
    <div>
      <IconBase name="lock" />
      <span>{{ connection.isLive ? `当前租户 · ${connection.tenantLabel}` : "本地演示 · 无需 API Key" }}</span>
    </div>
  </footer>
</template>
