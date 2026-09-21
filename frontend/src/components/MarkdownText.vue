<script setup lang="ts">
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { computed } from 'vue';

/**
 * Markdown rendering for model output.
 *
 * `marked` produces HTML, `DOMPurify` removes anything executable before it is
 * injected — model output is untrusted input, so sanitising is not optional.
 */
const props = withDefaults(defineProps<{ text: string; streaming?: boolean }>(), { streaming: false });

marked.setOptions({ gfm: true, breaks: true });

const html = computed(() => {
  const source = props.text ?? '';
  if (!source) return '';
  const rendered = marked.parse(source, { async: false }) as string;
  return DOMPurify.sanitize(rendered, { USE_PROFILES: { html: true } });
});
</script>

<template>
  <div class="markdown" :class="{ streaming }" v-html="html" />
</template>
