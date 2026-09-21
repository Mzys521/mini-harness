<script setup lang="ts">
import { computed } from 'vue';
import ActivityRow from '@/components/ActivityRow.vue';
import { TOOL_LABELS, type ToolCallView } from '@/stores/chat';

/**
 * One tool call: what the model asked for, whether it ran, and what came back.
 * Long payloads stay collapsed so a run with many calls remains readable.
 */
const props = defineProps<{ call: ToolCallView }>();
const type = computed(() => {
  const name = props.call.name.toLowerCase();
  if (/search|grep|find/.test(name)) return { icon: 'search', label: '搜索' };
  if (/read/.test(name)) return { icon: 'read', label: '读取' };
  if (/write|edit|patch/.test(name)) return { icon: 'edit', label: '编辑' };
  if (/command|exec|shell|pwsh|bash/.test(name)) return { icon: 'terminal', label: '执行' };
  if (/list|directory/.test(name)) return { icon: 'folder', label: '浏览' };
  return { icon: 'tool', label: '工具调用' };
});

const argumentText = computed(() => {
  const entries = Object.entries(props.call.arguments ?? {});
  if (!entries.length) return '';
  return entries
    .map(([key, value]) => `${key}=${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join('  ');
});

const preview = computed(() => {
  const args = props.call.arguments;
  const summary = args.description ?? args.path ?? args.query ?? args.pattern ?? args.command ?? args.argv;
  return Array.isArray(summary) ? summary.join(' ') : typeof summary === 'string' ? summary : props.call.name;
});
const body = computed(() => props.call.diff ? '' : props.call.output);
</script>

<template>
  <article class="tool-call" :class="`state-${call.state}`" :data-tool="call.name">
    <ActivityRow :icon="type.icon" :label="type.label" :preview="preview" :status="TOOL_LABELS[call.state]">
    <div class="tool-body">
      <span class="tool-name">{{ call.name }}</span>
      <pre v-if="argumentText" class="tool-arguments">{{ JSON.stringify(call.arguments, null, 2) }}</pre>
      <template v-if="call.diff">
        <div class="diff">
          <div class="diff-side"><span class="diff-label">修改前</span><pre>{{ call.diff.before }}</pre></div>
          <div class="diff-side"><span class="diff-label">修改后</span><pre>{{ call.diff.after }}</pre></div>
        </div>
      </template>
      <pre v-else-if="body" class="tool-output">{{ body }}</pre>
      <p v-else-if="call.state !== 'running'" class="tool-empty">该调用没有返回内容。</p>
    </div>
    </ActivityRow>
  </article>
</template>
