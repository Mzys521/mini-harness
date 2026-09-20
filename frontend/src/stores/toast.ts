import { defineStore } from "pinia";
import { ref } from "vue";

import type { ToastMessage } from "@/types/domain";

const DISMISS_MS = 3200;

export const useToastStore = defineStore("toast", () => {
  const messages = ref<ToastMessage[]>([]);
  let seq = 0;

  function push(text: string): void {
    const id = ++seq;
    messages.value = [...messages.value, { id, text }];
    window.setTimeout(() => dismiss(id), DISMISS_MS);
  }

  function dismiss(id: number): void {
    messages.value = messages.value.filter((message) => message.id !== id);
  }

  return { messages, push, dismiss };
});
