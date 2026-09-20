<script setup lang="ts">
import { iconPaths } from "@/ui/icons";

withDefaults(
  defineProps<{
    name: string;
    size?: number | string;
  }>(),
  { size: undefined },
);
</script>

<template>
  <span class="icon-inline" :data-icon="name">
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
      :style="size === undefined ? undefined : { width: `${size}px`, height: `${size}px` }"
      v-html="iconPaths(name)"
    />
  </span>
</template>
