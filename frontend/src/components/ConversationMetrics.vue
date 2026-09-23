<script setup lang="ts">
import { computed } from 'vue';
import AppIcon from '@/components/AppIcon.vue';
import { metricOptions, useAppearance } from '@/stores/appearance';
import type { Turn } from '@/stores/chat';

const props = defineProps<{ turns: Turn[] }>();
const appearance = useAppearance();
const number = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n));
const items = computed(() => {
  const turn = props.turns.at(-1);
  const metrics = Object.entries(turn?.metrics ?? {}).sort(([a], [b]) => Number(a) - Number(b)).map(([, m]) => m);
  const latest = metrics.at(-1);
  const sum = (key: 'input_tokens' | 'output_tokens' | 'duration_ms') => metrics.reduce((n, m) => n + m[key], 0);
  const input = sum('input_tokens'), duration = sum('duration_ms');
  const hasUsage = metrics.length > 0 && metrics.some(m => m.total_tokens > 0);
  const cacheKnown = input > 0 && metrics.every(m => m.cached_input_tokens !== null);
  const cached = metrics.reduce((n, m) => n + (m.cached_input_tokens ?? 0), 0);
  const contextKnown = latest && latest.total_tokens > 0 && latest.context_window;
  const remaining = contextKnown ? Math.max(0, latest.context_window! - latest.input_tokens - latest.output_tokens) : null;
  const values = {
    cache: { text: `缓存命中 ${cacheKnown ? `${(cached / input * 100).toFixed(0)}%` : '—'}`, title: cacheKnown ? `最近一轮：缓存输入 ${cached} / 输入 ${input} token` : '最近一轮尚无完整缓存用量报告' },
    speed: { text: `${hasUsage && duration > 0 ? (sum('output_tokens') / (duration / 1000)).toFixed(1) : '—'} tok/s`, title: '最近一轮平均输出速度：输出 token / 模型请求耗时，包含首字等待，不含工具执行和审批等待；请求结束后更新' },
    tokens: { text: `已用 ${turn && turn.tokens > 0 ? number(turn.tokens) : hasUsage ? '0' : '—'} tok`, title: `最近一轮各模型请求累计用量：${turn?.tokens ?? 0} token（输入 + 输出，含重复上下文）；不是当前上下文占用` },
    context: { text: `上下文余量 ${remaining === null ? '—' : `≈${number(remaining)} tok`}`, title: contextKnown ? `估算：配置窗口 ${latest.context_window} − 最近请求输入 ${latest.input_tokens} − 输出 ${latest.output_tokens}。不含未发送草稿及下次新增指令，不代表模型实际最大窗口。` : '尚无最近请求用量或窗口配置；精确上下文计算已列入规划' },
    steps: { text: `${props.turns.length} 轮 · ${metrics.length || '—'} 步`, title: '当前会话轮数 · 最近一轮已完成的模型请求数；旧记录可能没有步数明细' },
  };
  return metricOptions.filter(item => appearance.metrics[item.key]).map(item => ({ ...item, ...values[item.key] }));
});
</script>

<template>
  <div v-if="items.length" class="conversation-metrics" aria-label="对话用量指标">
    <span v-for="item in items" :key="item.key" :title="item.title" tabindex="0" :aria-label="`${item.text}。${item.title}`"><AppIcon :name="item.icon" />{{ item.text }}</span>
  </div>
</template>
