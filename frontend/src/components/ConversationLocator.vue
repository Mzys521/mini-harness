<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue';
import { STATUS_LABELS, type Turn } from '@/stores/chat';

const props = defineProps<{ turns: Turn[]; scroller: HTMLElement | null }>();
const emit = defineEmits<{ navigate: [] }>();
const active = ref(''), hovered = ref('');
const rail = ref<HTMLElement | null>(null);
const previewTop = ref(0);
const preview = computed(() => props.turns.find(turn => turn.id === hovered.value));
const summary = (text: string) => text.replace(/\s+/g, ' ').trim().slice(0, 100) || '未命名对话';
const reply = computed(() => {
  const block = [...(preview.value?.blocks ?? [])].reverse().find(block => block.kind === 'text' && !block.activity);
  return block?.kind === 'text' ? summary(block.text) : '';
});
let frame = 0;
let disconnect: (() => void) | undefined;
function articles(): HTMLElement[] { return Array.from(props.scroller?.querySelectorAll<HTMLElement>('.turn[data-run]') ?? []); }
function updateActive(): void {
  const scroller = props.scroller;
  if (!scroller || !props.turns.length) { active.value = ''; return; }
  if (scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 8) {
    active.value = props.turns.at(-1)!.id; return;
  }
  const anchor = scroller.getBoundingClientRect().top + Math.min(100, scroller.clientHeight * .25);
  const items = articles();
  let current = items[0]?.dataset.run ?? '';
  for (const item of items) {
    if (item.getBoundingClientRect().top > anchor) break;
    current = item.dataset.run ?? current;
  }
  active.value = current;
}
function schedule(): void {
  if (frame) return;
  frame = requestAnimationFrame(() => { frame = 0; updateActive(); });
}
function jump(id: string): void {
  const scroller = props.scroller, target = articles().find(item => item.dataset.run === id);
  if (!scroller || !target) return;
  emit('navigate');
  active.value = id;
  const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 32;
  scroller.scrollTo({ top: Math.max(0, top), behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
}
function show(id: string, event: Event): void {
  hovered.value = id;
  const button = event.currentTarget as HTMLElement, box = rail.value?.getBoundingClientRect();
  if (box) previewTop.value = Math.max(48, Math.min(box.height - 48, button.getBoundingClientRect().top - box.top + button.offsetHeight / 2));
}
function onKey(event: KeyboardEvent): void {
  const buttons = Array.from(rail.value?.querySelectorAll<HTMLButtonElement>('button') ?? []);
  const index = buttons.indexOf(event.target as HTMLButtonElement);
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : event.key === 'ArrowDown' ? Math.min(index + 1, buttons.length - 1) : event.key === 'ArrowUp' ? Math.max(index - 1, 0) : -1;
  if (next >= 0) { event.preventDefault(); buttons[next]?.focus(); }
  if (event.key === 'Escape') hovered.value = '';
}
watch(() => [props.scroller, props.turns.map(turn => turn.id).join('|')], async (_, __, onCleanup) => {
  let stale = false;
  onCleanup(() => { stale = true; disconnect?.(); });
  hovered.value = '';
  await nextTick();
  if (stale || !props.scroller) return;
  const scroller = props.scroller, observer = new ResizeObserver(schedule);
  observer.observe(scroller); articles().forEach(item => observer.observe(item));
  scroller.addEventListener('scroll', schedule, { passive: true });
  disconnect = () => { observer.disconnect(); scroller.removeEventListener('scroll', schedule); };
  schedule();
}, { immediate: true, flush: 'post' });
onUnmounted(() => { disconnect?.(); cancelAnimationFrame(frame); });
</script>

<template>
  <aside v-if="turns.length" ref="rail" class="conversation-locator" @mouseleave="hovered = ''">
    <nav aria-label="对话快速定位" class="locator-marks" @keydown="onKey">
      <button v-for="(turn, index) in turns" :key="turn.id" type="button" :aria-label="`跳转到第 ${index + 1} 轮对话：${summary(turn.input)}`" :aria-current="active === turn.id ? 'location' : undefined" :aria-describedby="hovered === turn.id ? 'locator-preview' : undefined" @mouseenter="show(turn.id, $event)" @focus="show(turn.id, $event)" @blur="hovered = ''" @click="jump(turn.id)">
        <span class="locator-mark" :style="{ '--mark-width': `${Math.min(28, 12 + turn.input.length / 6)}px` }" />
      </button>
    </nav>
    <div v-if="preview" id="locator-preview" role="tooltip" class="locator-preview" :style="{ top: `${previewTop}px` }">
      <small>第 {{ turns.findIndex(turn => turn.id === preview?.id) + 1 }} 轮 · {{ STATUS_LABELS[preview.status] }}</small>
      <strong>{{ summary(preview.input) }}</strong>
      <p v-if="reply">{{ reply }}</p>
      <span>点击定位此轮对话</span>
    </div>
  </aside>
</template>
