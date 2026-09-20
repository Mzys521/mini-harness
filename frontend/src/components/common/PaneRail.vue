<script setup lang="ts">
import IconBase from "@/components/common/IconBase.vue";

/**
 * The resting state of a collapsed pane. It stays visible and reachable
 * instead of vanishing, so the workspace never loses an entry point.
 */
defineProps<{
  icon: string;
  title: string;
  controls: string;
  count?: number | string | null;
}>();

const emit = defineEmits<{ expand: [] }>();
</script>

<template>
  <button
    class="pane-rail"
    type="button"
    :aria-expanded="false"
    :aria-controls="controls"
    :aria-label="`展开${title}`"
    :title="`展开${title}`"
    @click="emit('expand')"
  >
    <span class="pane-rail-icon"><IconBase :name="icon" /></span>
    <span class="pane-rail-title">{{ title }}</span>
    <span v-if="count !== undefined && count !== null" class="pane-rail-count">{{ count }}</span>
    <span class="pane-rail-toggle" aria-hidden="true"><IconBase name="panel-expand" /></span>
  </button>
</template>
