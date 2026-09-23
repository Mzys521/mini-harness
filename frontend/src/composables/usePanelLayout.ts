import { computed, onBeforeUnmount, onMounted, reactive, ref, type Ref } from 'vue';
import { readJSON, writeJSON } from '@/api/storage';

export const LAYOUT_KEY = 'mini-harness.layout.v1';
export const LAYOUT_DEFAULTS = { sidebarWidth: 264, sidebarHeight: 230, composerHeight: 164 };
type Sizes = typeof LAYOUT_DEFAULTS;

export function usePanelLayout(root: Ref<HTMLElement | null>, main: Ref<HTMLElement | null>) {
  const stored = readJSON<Partial<Sizes>>(LAYOUT_KEY);
  const sizes = reactive({ ...LAYOUT_DEFAULTS });
  for (const key of Object.keys(sizes) as (keyof Sizes)[]) {
    const value = stored?.[key];
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) sizes[key] = value;
  }
  const width = ref(window.innerWidth);
  const height = ref(window.innerHeight);
  const mainHeight = ref(window.innerHeight);
  const narrow = computed(() => width.value <= 720);
  const sidebarMax = computed(() => narrow.value ? Math.floor(height.value * .4) : Math.max(220, Math.min(520, width.value - 368)));
  const sidebarMin = computed(() => Math.min(narrow.value ? 120 : 220, sidebarMax.value));
  const sidebarDefault = computed(() => narrow.value ? LAYOUT_DEFAULTS.sidebarHeight : LAYOUT_DEFAULTS.sidebarWidth);
  const composerMax = computed(() => Math.max(140, Math.min(480, Math.floor(mainHeight.value * .5))));
  const composerMin = computed(() => Math.min(140, composerMax.value));
  const clamp = (value: number, min: number, max: number) => Math.round(Math.max(min, Math.min(max, value)));
  // Constrain the rendered size without overwriting preferences when the window shrinks.
  const sidebarSize = computed({
    get: () => clamp(narrow.value ? sizes.sidebarHeight : sizes.sidebarWidth, sidebarMin.value, sidebarMax.value),
    set: (value: number) => { sizes[narrow.value ? 'sidebarHeight' : 'sidebarWidth'] = clamp(value, sidebarMin.value, sidebarMax.value); },
  });
  const composerSize = computed({
    get: () => clamp(sizes.composerHeight, composerMin.value, composerMax.value),
    set: (value: number) => { sizes.composerHeight = clamp(value, composerMin.value, composerMax.value); },
  });
  const save = () => writeJSON(LAYOUT_KEY, { ...sizes });

  function measure(): void {
    width.value = root.value?.clientWidth || window.innerWidth;
    height.value = root.value?.clientHeight || window.innerHeight;
    mainHeight.value = main.value?.clientHeight || height.value;
  }
  let observer: ResizeObserver | undefined;
  onMounted(() => {
    measure();
    observer = new ResizeObserver(measure);
    if (root.value) observer.observe(root.value);
    if (main.value) observer.observe(main.value);
    window.addEventListener('resize', measure);
  });
  onBeforeUnmount(() => {
    observer?.disconnect();
    window.removeEventListener('resize', measure);
  });
  return { narrow, sidebarSize, sidebarMin, sidebarMax, sidebarDefault, composerSize, composerMin, composerMax, save };
}
