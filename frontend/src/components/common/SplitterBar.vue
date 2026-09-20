<script setup lang="ts">
import { computed, ref } from "vue";

import IconBase from "@/components/common/IconBase.vue";

/**
 * Pane edge that resizes its neighbour. Implemented with Pointer Events so
 * mouse, pen and touch behave the same, and fully keyboard operable:
 * arrows nudge, Shift+arrows move further, Home restores the default ratio.
 */
const props = withDefaults(
  defineProps<{
    orientation: "vertical" | "horizontal";
    label: string;
    controls: string;
    min: number;
    max: number;
    step?: number;
    bigStep?: number;
    /** Multiplier applied to pointer movement (the two inspector edges differ). */
    direction?: 1 | -1;
  }>(),
  { step: 10, bigStep: 30, direction: 1 },
);

const value = defineModel<number>({ required: true });
const emit = defineEmits<{ reset: [] }>();

const dragging = ref(false);
let drag: { pointerId: number; origin: number; start: number } | null = null;

const isVertical = computed(() => props.orientation === "vertical");

function onPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return;
  const element = event.currentTarget as HTMLElement;
  drag = {
    pointerId: event.pointerId,
    origin: isVertical.value ? event.clientX : event.clientY,
    start: value.value,
  };
  element.setPointerCapture(event.pointerId);
  dragging.value = true;
  document.body.classList.add("resizing");
  if (!isVertical.value) document.body.classList.add("resizing-y");
  event.preventDefault();
}

function onPointerMove(event: PointerEvent): void {
  if (!drag || event.pointerId !== drag.pointerId) return;
  const current = isVertical.value ? event.clientX : event.clientY;
  value.value = drag.start + (current - drag.origin) * props.direction;
}

function finish(): void {
  if (!drag) return;
  drag = null;
  dragging.value = false;
  document.body.classList.remove("resizing", "resizing-y");
}

function onKeydown(event: KeyboardEvent): void {
  const back = isVertical.value ? "ArrowLeft" : "ArrowUp";
  const forward = isVertical.value ? "ArrowRight" : "ArrowDown";
  if (![back, forward, "Home"].includes(event.key)) return;
  event.preventDefault();
  if (event.key === "Home") {
    emit("reset");
    return;
  }
  const distance = (event.shiftKey ? props.bigStep : props.step) * props.direction;
  value.value = value.value + (event.key === forward ? distance : -distance);
}
</script>

<template>
  <div
    class="splitter"
    :class="[orientation, { dragging }]"
    role="separator"
    tabindex="0"
    :aria-label="label"
    :aria-orientation="orientation"
    :aria-controls="controls"
    :aria-valuemin="Math.round(min)"
    :aria-valuemax="Math.round(max)"
    :aria-valuenow="Math.round(value)"
    title="拖动调整大小；双击还原；方向键微调"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="finish"
    @pointercancel="finish"
    @lostpointercapture="finish"
    @dblclick="emit('reset')"
    @keydown="onKeydown"
  />
</template>
