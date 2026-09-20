import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import App from "@/App.vue";
import { STORAGE_KEYS } from "@/api/storage";
import { setViewportWidth } from "@/__tests__/setup";
import { useInspectorStore } from "@/stores/inspector";

function mountApp() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(App, { global: { plugins: [pinia] } });
  return { wrapper, layout: useInspectorStore(pinia) };
}

function toggleButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.find(".pane-toggle");
}

/** The run-log control is a header toggle when open and a rail when folded. */
function activityToggle(wrapper: ReturnType<typeof mount>) {
  const header = wrapper.find(".activity-pane .pane-toggle");
  return header.exists() ? header : wrapper.find(".activity-pane .pane-rail");
}

function rails(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll(".pane-rail");
}

function persisted() {
  const raw = localStorage.getItem(STORAGE_KEYS.layout);
  return raw ? JSON.parse(raw) : null;
}

describe("collapsible right-hand panes", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders both panes expanded with the remembered ratio", () => {
    const { wrapper } = mountApp();
    expect(wrapper.find(".workspace").classes()).toContain("inspector-both-open");
    expect(wrapper.find(".context-content").exists()).toBe(true);
    expect(wrapper.find(".activity-content").exists()).toBe(true);
    expect(rails(wrapper)).toHaveLength(0);
    expect(wrapper.find(".splitter.horizontal").exists()).toBe(true);
  });

  it("folds the context pane into a rail and shrinks the inspector column", async () => {
    const { wrapper, layout } = mountApp();
    await toggleButton(wrapper).trigger("click");

    expect(layout.contextFolded).toBe(true);
    expect(wrapper.find(".context-pane").classes()).toContain("is-collapsed");
    expect(wrapper.find(".context-content").exists()).toBe(false);
    // The column keeps its track but collapses to the rail width.
    expect(wrapper.find(".workspace").attributes("style")).toContain(
      "--inspector-width: var(--pane-rail-width)",
    );
    // The expansion affordance stays reachable.
    expect(rails(wrapper)).toHaveLength(1);
    expect(persisted().contextCollapsed).toBe(true);
  });

  it("folds the run-log pane and hides the height splitter when only one pane is open", async () => {
    const { wrapper, layout } = mountApp();
    await activityToggle(wrapper).trigger("click");

    expect(layout.activityFolded).toBe(true);
    expect(wrapper.find(".activity-content").exists()).toBe(false);
    expect(wrapper.find(".workspace").classes()).not.toContain("inspector-both-open");
    // Nothing left to resize, so the splitter must not linger.
    expect(wrapper.find(".splitter.horizontal").exists()).toBe(false);
  });

  it("restores the pane from its rail and keeps the previous ratio", async () => {
    const { wrapper, layout } = mountApp();
    layout.contextRatio = 0.5;
    await toggleButton(wrapper).trigger("click");
    expect(layout.contextFolded).toBe(true);

    const rail = wrapper.find(".context-pane .pane-rail");
    expect(rail.exists()).toBe(true);
    await rail.trigger("click");

    expect(layout.contextFolded).toBe(false);
    expect(layout.contextRatio).toBe(0.5);
    expect(wrapper.find(".context-content").exists()).toBe(true);
  });

  it("keeps both panes open when a run log needs room, at the same ratio", async () => {
    const { wrapper, layout } = mountApp();
    layout.contextRatio = 0.4;
    // Re-query each time: folding re-renders the panes, so element handles from
    // before the click are detached.
    await activityToggle(wrapper).trigger("click");
    await activityToggle(wrapper).trigger("click");

    expect(layout.activityFolded).toBe(false);
    expect(wrapper.find(".workspace").classes()).toContain("inspector-both-open");
    expect(wrapper.find(".workspace").attributes("style")).toContain("--context-height: 40%");
  });

  it("folds the context pane with Ctrl+B", async () => {
    const { wrapper, layout } = mountApp();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "b", ctrlKey: true }));
    await wrapper.vm.$nextTick();
    expect(layout.contextFolded).toBe(true);
  });

  it("folds the run log with Ctrl+J", async () => {
    const { wrapper, layout } = mountApp();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "j", ctrlKey: true }));
    await wrapper.vm.$nextTick();
    expect(layout.activityFolded).toBe(true);
  });

  it("ignores collapse state on a narrow viewport", () => {
    // The mobile breakpoint switches views instead of folding panes, so a
    // persisted fold flag must not hide either pane there.
    setViewportWidth(600);
    try {
      const { wrapper, layout } = mountApp();
      layout.contextCollapsed = true;
      expect(layout.isMobile).toBe(true);
      expect(layout.contextFolded).toBe(false);
      expect(wrapper.find(".context-content").exists()).toBe(true);
    } finally {
      setViewportWidth(1440);
    }
  });
});

describe("inspector persistence", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("stores widths, ratio and folded flags in one layout record", async () => {
    const { wrapper, layout } = mountApp();
    layout.sidebar = 260;
    layout.inspector = 400;
    layout.contextRatio = 0.55;
    await toggleButton(wrapper).trigger("click");
    await wrapper.vm.$nextTick();

    expect(persisted()).toMatchObject({
      sidebar: 260,
      inspector: 400,
      context: 0.55,
      contextCollapsed: true,
      activityCollapsed: false,
    });
  });

  it("resets both panes and the ratio together", () => {
    const { layout } = mountApp();
    layout.contextCollapsed = true;
    layout.activityCollapsed = true;
    layout.contextRatio = 0.2;

    layout.resetLayout();

    expect(layout.contextFolded).toBe(false);
    expect(layout.activityFolded).toBe(false);
    expect(layout.contextRatio).toBeCloseTo(0.65, 5);
  });
});
