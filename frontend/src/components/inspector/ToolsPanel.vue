<script setup lang="ts">
import IconBase from "@/components/common/IconBase.vue";
import { toolCatalog } from "@/data/catalog";
</script>

<template>
  <div class="tools-content">
    <div v-for="tool in toolCatalog" :key="tool.reference" class="tool-row">
      <span :data-icon="tool.icon"><IconBase :name="tool.icon" /></span>
      <div>
        <strong>{{ tool.name }}</strong>
        <p>{{ tool.description }}</p>
        <code>{{ tool.reference }}</code>
      </div>
    </div>
    <p class="tools-note">项目能力概览。实际可用工具与权限由连接后的服务端配置决定。</p>
  </div>
</template>
