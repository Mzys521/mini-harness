<script setup lang="ts">
withDefaults(defineProps<{ name?: string }>(), { name: 'tool' });
const paths: Record<string, string> = {
  gauge: 'M4 18a9 9 0 1 1 16 0M12 13l4-6M11 13a1 1 0 1 0 2 0 1 1 0 0 0-2 0',
  tokens: 'M20 6c0 2-16 2-16 0s16-2 16 0ZM4 6v6c0 2 16 2 16 0V6M4 12v6c0 2 16 2 16 0v-6',
  cache: 'M20 8a8 8 0 0 0-13-3L4 8m0-5v5h5M4 16a8 8 0 0 0 13 3l3-3m0 5v-5h-5',
  context: 'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M8 12h8',

  palette: 'M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1-3.7 1.5 1.5 0 0 1 1-2.8h2a4 4 0 0 0 4-4A8.5 8.5 0 0 0 12 3ZM7 9h.01M11 6h.01M16 7h.01M6 13h.01',
  temporary: 'M21 11.5a8.5 8.5 0 0 1-8.5 8.5 9 9 0 0 1-4-1L3 21l2-5.5a9 9 0 0 1-1-4A8.5 8.5 0 0 1 12.5 3a8.5 8.5 0 0 1 8.5 8.5Z',
  skill: 'M12 3 3 7l9 4 9-4zM5 11v6l7 4 7-4v-6M12 11v10',
  plus: 'M12 4v16M4 12h16',
  compose: 'M12 4H6a3 3 0 0 0-3 3v11a3 3 0 0 0 3 3h11a3 3 0 0 0 3-3v-6M14 5l4 4M10 13l-1 4 4-1 9-9-3-3z',
  branch: 'M6 7v10m12-10v6a4 4 0 0 1-4 4h-2m3-3-3 3 3 3M9 4a3 3 0 1 1-6 0 3 3 0 0 1 6 0M9 20a3 3 0 1 1-6 0 3 3 0 0 1 6 0M21 4a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  clock: 'M12 7v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  plugin: 'M9 3h6v4h4v4h-4v4H9v-4H5V7h4zM3 15v6h18v-6',
  explore: 'M4 12h1m6 0h1m6 0h1',
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
  'arrow-up': 'M12 20V4m-7 7 7-7 7 7',
  shield: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6zm-4 9 3 3 5-6',
  stop: 'M6 6h12v12H6z',
};
</script>

<template>
  <svg class="app-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="paths[name] ?? paths.tool" :stroke-dasharray="name === 'temporary' ? '5 3' : undefined" />
  </svg>
</template>
