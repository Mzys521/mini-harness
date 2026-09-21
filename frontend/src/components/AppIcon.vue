<script setup lang="ts">
withDefaults(defineProps<{ name?: string }>(), { name: 'tool' });
const paths: Record<string, string> = {
  thought: 'M9 18h6m-5 3h4M8 15c0-2-3-3-3-7a7 7 0 0 1 14 0c0 4-3 5-3 7v1H8z',
  read: 'M8 3h9a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6zm1 5h6m-6 4h6m-6 4h3',
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  terminal: 'M8 8l4 4-4 4m6 0h3M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2',
  edit: 'M14 5l5 5M4 20l5-1L21 7l-4-4L5 15zm0 0h16',
  folder: 'M3 6h7l2 2h9v12H3zm0 0V4h7l2 2',
  step: 'M9 6h12M9 12h12M9 18h12M3 5l1 1 2-2M3 11l1 1 2-2M3 17l1 1 2-2',
  tool: 'M14 3a6 6 0 0 0-7 8L2 16a3 3 0 0 0 4 4l5-5a6 6 0 0 0 8-7l-4 4-3-3z',
  settings: 'M4 7h16M4 17h16M9 4v6m6 4v6',
  chevron: 'M9 5l7 7-7 7',
  close: 'M6 6l12 12M18 6L6 18',
};
</script>

<template>
  <svg class="app-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="paths[name] ?? paths.tool" />
  </svg>
</template>
