<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';

const props = defineProps<{
  modelValue: number;
  min: number;
  max: number;
  defaultValue: number;
  orientation: 'vertical' | 'horizontal';
  label: string;
  controls: string;
  reverse?: boolean;
}>();
const emit = defineEmits<{ 'update:modelValue': [value: number]; commit: [] }>();
const handle = ref<HTMLElement | null>(null);
const dragging = ref(false);
let pointerId: number | null = null;
let startPosition = 0;
let startSize = 0;

function update(value: number): void {
  emit('update:modelValue', Math.round(Math.max(props.min, Math.min(props.max, value))));
}

function position(event: PointerEvent): number {
  return props.orientation === 'vertical' ? event.clientX : event.clientY;
}

function start(event: PointerEvent): void {
  if (event.button !== 0 || event.isPrimary === false || pointerId !== null) return;
  event.preventDefault();
  handle.value?.focus();
  pointerId = event.pointerId;
  startPosition = position(event);
  startSize = props.modelValue;
  handle.value?.setPointerCapture(event.pointerId);
  dragging.value = true;
  window.addEventListener('blur', finish);
}

function move(event: PointerEvent): void {
  if (event.pointerId !== pointerId) return;
  update(startSize + (position(event) - startPosition) * (props.reverse ? -1 : 1));
}

function finish(): void {
  if (pointerId === null) return;
  const id = pointerId;
  pointerId = null;
  dragging.value = false;
  window.removeEventListener('blur', finish);
  if (handle.value?.hasPointerCapture(id)) handle.value.releasePointerCapture(id);
  emit('commit');
}

function cancel(): void {
  if (pointerId === null) return;
  update(startSize);
  finish();
}

function reset(): void {
  update(props.defaultValue);
  emit('commit');
}

function keydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && dragging.value) { event.preventDefault(); cancel(); return; }
  const negative = props.orientation === 'vertical' ? 'ArrowLeft' : 'ArrowUp';
  const positive = props.orientation === 'vertical' ? 'ArrowRight' : 'ArrowDown';
  if (![negative, positive, 'Home', 'End', 'Enter'].includes(event.key)) return;
  event.preventDefault();
  if (event.key === 'Enter') { reset(); return; }
  const delta = (event.shiftKey ? 40 : 10) * (props.reverse ? -1 : 1);
  update(event.key === 'Home' ? props.min : event.key === 'End' ? props.max
    : props.modelValue + (event.key === positive ? delta : -delta));
  emit('commit');
}

onBeforeUnmount(finish);
</script>

<template>
  <div ref="handle" class="resize-divider" :class="[orientation, { dragging }]" role="separator" tabindex="0"
    :aria-label="label" :aria-controls="controls" :aria-orientation="orientation"
    :aria-valuemin="min" :aria-valuemax="max" :aria-valuenow="modelValue" :aria-valuetext="`${modelValue} 像素`"
    :title="`${label}：拖动调整，双击恢复默认；方向键微调，Enter 恢复默认`"
    @pointerdown="start" @pointermove="move" @pointerup="event => { if (event.pointerId === pointerId) { move(event); finish(); } }"
    @pointercancel="cancel" @lostpointercapture="finish" @keydown="keydown" @dblclick="reset"
  />
</template>
