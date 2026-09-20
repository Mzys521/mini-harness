import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { useInspectorStore } from "@/stores/inspector";

/** Which modal surface is currently open. Only one may be open at a time. */
export type DialogName = "command" | "settings" | "attachment";

export const useUiStore = defineStore("ui", () => {
  const layout = useInspectorStore();
  const openDialog = ref<DialogName | null>(null);

  const anyDialogOpen = computed(() => openDialog.value !== null);
  const commandOpen = computed({
    get: () => openDialog.value === "command",
    set: (value: boolean) => {
      openDialog.value = value ? "command" : null;
    },
  });
  const settingsOpen = computed({
    get: () => openDialog.value === "settings",
    set: (value: boolean) => {
      openDialog.value = value ? "settings" : null;
    },
  });
  const attachmentOpen = computed({
    get: () => openDialog.value === "attachment",
    set: (value: boolean) => {
      openDialog.value = value ? "attachment" : null;
    },
  });

  function toggle(dialog: DialogName): void {
    openDialog.value = openDialog.value === dialog ? null : dialog;
  }

  function closeAll(): void {
    openDialog.value = null;
  }

  /** Both right-hand panes visible again, in their remembered ratio. */
  function showInspector(): void {
    layout.contextCollapsed = false;
    layout.activityCollapsed = false;
  }

  return {
    openDialog,
    anyDialogOpen,
    commandOpen,
    settingsOpen,
    attachmentOpen,
    toggle,
    closeAll,
    showInspector,
  };
});
