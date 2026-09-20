<script setup lang="ts">
import { computed } from "vue";

import { parseMarkdown } from "@/utils/format";

const props = defineProps<{ content: string }>();

/**
 * Markdown blocks are pre-escaped and only ever contain <strong>, <code> and
 * <pre>, because escaping happens before any tag is introduced.
 */
const segments = computed(() => parseMarkdown(props.content));
</script>

<template>
  <template v-for="(segment, index) in segments" :key="index">
    <pre v-if="segment.kind === 'code'"><code>{{ segment.source }}</code></pre>
    <template v-else>
      <p v-for="(paragraph, pIndex) in segment.paragraphs" :key="pIndex" v-html="paragraph" />
    </template>
  </template>
</template>
