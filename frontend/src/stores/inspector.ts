import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

import { STORAGE_KEYS, readJSON, writeJSON } from "@/api/storage";
import { useIsMobile } from "@/composables/useMediaQuery";
import type { ContextTab, MobileView, PersistedLayout, Theme } from "@/types/domain";

export const DEFAULT_LAYOUT = { sidebar: 232, inspector: 324, context: 0.65 } as const;
export const SIDEBAR_LIMITS = { min: 188, max: 320 } as const;
export const INSPECTOR_LIMITS = { min: 270, max: 520 } as const;
export const CONTEXT_LIMITS = { min: 0.35, max: 0.76 } as const;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

/**
 * Owns window layout: pane widths/ratio, which detail tab is visible, panel
 * collapsed state, mobile view and theme. Everything is persisted, and the
 * collapsed flags live next to the ratio so expanding restores the prior size.
 */
export const useInspectorStore = defineStore("inspector", () => {
  const restored = readJSON<PersistedLayout>(STORAGE_KEYS.layout);
  const isMobile = useIsMobile();

  const sidebar = ref(restored?.sidebar ?? DEFAULT_LAYOUT.sidebar);
  const inspector = ref(restored?.inspector ?? DEFAULT_LAYOUT.inspector);
  const contextRatio = ref(
    typeof restored?.context === "number"
      ? clamp(restored.context, CONTEXT_LIMITS.min, CONTEXT_LIMITS.max)
      : DEFAULT_LAYOUT.context,
  );
  const contextCollapsed = ref(restored?.contextCollapsed === true);
  const activityCollapsed = ref(restored?.activityCollapsed === true);
  const tab = ref<ContextTab>("context");
  const mobileView = ref<MobileView>("chat");
  const theme = ref<Theme>(readJSON<Theme>(STORAGE_KEYS.theme) === "dark" ? "dark" : "light");

  // Collapsing is a desktop affordance: on mobile a single view owns the
  // screen, so the right column must always render both panes stacked.
  const contextFolded = computed(() => !isMobile.value && contextCollapsed.value);
  const activityFolded = computed(() => !isMobile.value && activityCollapsed.value);

  const inspectorClass = computed(() => {
    if (!contextFolded.value && !activityFolded.value) return "inspector-both-open";
    return "inspector-single-pane";
  });

  function persistLayout(): void {
    writeJSON(STORAGE_KEYS.layout, {
      sidebar: sidebar.value,
      inspector: inspector.value,
      context: contextRatio.value,
      contextCollapsed: contextCollapsed.value,
      activityCollapsed: activityCollapsed.value,
    } satisfies PersistedLayout);
  }

  function toggleContext(): void {
    contextCollapsed.value = !contextCollapsed.value;
    persistLayout();
  }

  function toggleActivity(): void {
    activityCollapsed.value = !activityCollapsed.value;
    persistLayout();
  }

  function setTab(next: ContextTab): void {
    tab.value = next;
    // Choosing a tab is a request to see that pane.
    if (next === "tools") contextCollapsed.value = false;
  }

  function setMobileView(view: MobileView): void {
    mobileView.value = view;
  }

  function revealActivity(): void {
    activityCollapsed.value = false;
  }

  function resetLayout(): void {
    sidebar.value = DEFAULT_LAYOUT.sidebar;
    inspector.value = DEFAULT_LAYOUT.inspector;
    contextRatio.value = DEFAULT_LAYOUT.context;
    contextCollapsed.value = false;
    activityCollapsed.value = false;
    persistLayout();
  }

  function applyTheme(next: Theme): void {
    theme.value = next;
    document.documentElement.dataset.theme = next;
    writeJSON(STORAGE_KEYS.theme, next);
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    if (meta) meta.content = next === "dark" ? "#191b19" : "#f2f3f0";
  }

  function toggleTheme(): void {
    applyTheme(theme.value === "dark" ? "light" : "dark");
  }

  // Persist on the way out instead of on every pointer move.
  window.addEventListener("pagehide", persistLayout);
  watch([sidebar, inspector, contextRatio], persistLayout);

  return {
    sidebar,
    inspector,
    contextRatio,
    contextCollapsed,
    activityCollapsed,
    contextFolded,
    activityFolded,
    inspectorClass,
    tab,
    mobileView,
    theme,
    isMobile,
    persistLayout,
    toggleContext,
    toggleActivity,
    setTab,
    setMobileView,
    revealActivity,
    resetLayout,
    applyTheme,
    toggleTheme,
  };
});
