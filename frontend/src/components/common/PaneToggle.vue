<script setup lang="ts">
import { computed } from "vue";

import IconBase from "@/components/common/IconBase.vue";

/**
 * Folds a pane into its rail, or restores it. The label and icon direction
 * follow the pane's axis so the affordance reads correctly for both the
 * side-by-side and stacked layouts.
 */
const props = withDefaults(
  defineProps<{
    collapsed: boolean;
    controls: string;
    axis?: "vertical" | "horizontal";
    label?: string;
  }>(),
  { axis: "horizontal", label: "" },
);

const emit = defineEmits<{ toggle: [] }>();

const icon = computed(() => {
  if (props.axis === "horizontal") {
    return props.collapsed ? "panel-bottom-expand" : "panel-bottom-collapse";
  }
  return props.collapsed ? "panel-expand" : "panel-collapse";
});

const ariaLabel = computed(() => {
  const subject = props.label || "面板";
  return props.collapsed ? `展开${subject}` : `折叠${subject}`;
});
</script>

<template>
  <button
    class="icon-button small pane-toggle"
    type="button"
    :aria-expanded="!collapsed"
    :aria-controls="controls"
    :aria-label="ariaLabel"
    :title="ariaLabel"
    @click.stop="emit('toggle')"
  >
    <IconBase :name="icon" />
  </button>
</template>
