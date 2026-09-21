<script setup lang="ts">
import { ref, useId } from 'vue';
import AppIcon from '@/components/AppIcon.vue';

defineProps<{ icon: string; label: string; preview?: string; status?: string }>();
const open = ref(false);
const bodyId = useId();
</script>

<template>
  <div class="activity-row" :class="{ expanded: open }">
    <button type="button" class="activity-toggle" :aria-expanded="open" :aria-controls="bodyId" @click="open = !open">
      <AppIcon :name="icon" />
      <span class="activity-label">{{ label }}</span>
      <span v-if="preview" class="activity-separator" aria-hidden="true">·</span>
      <span class="activity-preview">{{ preview }}</span>
      <span v-if="status" class="activity-status">{{ status }}</span>
      <AppIcon name="chevron" class="activity-chevron" />
    </button>
    <div v-show="open" :id="bodyId" class="activity-body"><slot /></div>
  </div>
</template>
