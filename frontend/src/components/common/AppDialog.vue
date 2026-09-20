<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import IconBase from "@/components/common/IconBase.vue";

/**
 * Native <dialog> wrapper: keeps the browser's focus trap, Escape handling and
 * ::backdrop, while letting the parent use declarative `v-model:open`.
 */
const props = withDefaults(
  defineProps<{
    title?: string;
    labelId?: string;
    className?: string;
    closeOnBackdrop?: boolean;
    initialFocus?: string;
  }>(),
  { title: "", labelId: undefined, className: "", closeOnBackdrop: true, initialFocus: "" },
);

const open = defineModel<boolean>("open", { required: true });
const emit = defineEmits<{ close: [] }>();

const element = ref<HTMLDialogElement | null>(null);

function close(): void {
  open.value = false;
  emit("close");
}

function onBackdropClick(event: MouseEvent): void {
  if (!props.closeOnBackdrop) return;
  if (event.target !== element.value) return;
  const bounds = element.value.getBoundingClientRect();
  const outside =
    event.clientX < bounds.left ||
    event.clientX > bounds.right ||
    event.clientY < bounds.top ||
    event.clientY > bounds.bottom;
  if (outside) close();
}

watch(open, (value) => {
  const node = element.value;
  if (!node) return;
  if (value && !node.open) {
    node.showModal();
    if (props.initialFocus) {
      node.querySelector<HTMLElement>(props.initialFocus)?.focus();
    }
  } else if (!value && node.open) {
    node.close();
  }
});

onMounted(() => {
  if (open.value) element.value?.showModal();
});

onBeforeUnmount(() => {
  if (element.value?.open) element.value.close();
});

defineExpose({ close });
</script>

<template>
  <dialog
    ref="element"
    :class="className"
    :aria-labelledby="labelId"
    @click="onBackdropClick"
    @close="open = false"
    @cancel="open = false"
  >
    <slot :close="close" />
  </dialog>
</template>
