import { defineStore } from 'pinia';
import { computed, ref, watch } from 'vue';
import { readJSON, writeJSON } from '@/api/storage';

export const metricOptions = [
  { key: 'cache', label: '缓存命中率', icon: 'cache' },
  { key: 'speed', label: '输出速度', icon: 'gauge' },
  { key: 'tokens', label: '已用 token', icon: 'tokens' },
  { key: 'context', label: '上下文余量', icon: 'context' },
  { key: 'steps', label: '对话轮数与模型步数', icon: 'step' },
] as const;
type MetricKey = typeof metricOptions[number]['key'];
export const APPEARANCE_KEY = 'mini-harness.appearance.v1';
export const themes = [
  { value: 'dark', label: '深色', note: '静夜' },
  { value: 'light', label: '浅色', note: '晨光' },
  { value: 'paper', label: '暖纸色', note: '书页' },
  { value: 'system', label: '跟随系统', note: '自动切换' },
] as const;
export const fonts = [
  { value: 'serif', label: '衬线体', note: '宋体 / Georgia · 书页般的阅读感' },
  { value: 'sans', label: '无衬线体', note: '系统字体 · 简洁清晰' },
  { value: 'mono', label: '等宽体', note: 'Consolas · 工整有序' },
] as const;
type Theme = typeof themes[number]['value'];
type Font = typeof fonts[number]['value'];
export const DEFAULT_PALETTE = { background: '#131413', surface: '#1a1c1a', text: '#e9ece7', border: '#3b3d38' };
export const paletteFields = [
  { key: 'background', label: '页面背景' }, { key: 'surface', label: '侧栏与面板' },
  { key: 'text', label: '正文颜色' }, { key: 'border', label: '边框颜色' },
] as const;
export function isColor(value: unknown): value is string { return typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value); }
function luminance(color: string): number {
  const rgb = [1, 3, 5].map(start => parseInt(color.slice(start, start + 2), 16) / 255)
    .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
  return rgb[0]! * .2126 + rgb[1]! * .7152 + rgb[2]! * .0722;
}
export function contrast(a: string, b: string): number {
  const x = luminance(a), y = luminance(b);
  return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}

export const useAppearance = defineStore('appearance', () => {
  const saved = readJSON<{ theme?: Theme; font?: Font; metrics?: Partial<Record<MetricKey, boolean>>; customColors?: boolean; customAccent?: boolean; accent?: string; palette?: Partial<typeof DEFAULT_PALETTE> }>(APPEARANCE_KEY);
  const metrics = ref<Record<MetricKey, boolean>>({ cache: true, speed: true, tokens: true, context: true, steps: false });
  for (const { key } of metricOptions) if (typeof saved?.metrics?.[key] === 'boolean') metrics.value[key] = saved.metrics[key]!;
  const theme = ref<Theme>(themes.some(item => item.value === saved?.theme) ? saved!.theme! : 'dark');
  const font = ref<Font>(fonts.some(item => item.value === saved?.font) ? saved!.font! : 'serif');
  const customColors = ref(saved?.customColors === true);
  const customAccent = ref(saved?.customAccent === true);
  const accent = ref(isColor(saved?.accent) ? saved.accent : '#d6ad60');
  const palette = ref({ ...DEFAULT_PALETTE });
  for (const { key } of paletteFields) if (isColor(saved?.palette?.[key])) palette.value[key] = saved!.palette![key]!;
  const paletteContrast = computed(() => Math.min(contrast(palette.value.text, palette.value.background), contrast(palette.value.text, palette.value.surface)));
  const colorTokens = ['--bg', '--bg-raised', '--bg-input', '--composer-bg', '--composer-line', '--line', '--line-soft', '--text', '--text-dim', '--text-faint', '--hover', '--selected', '--accent', '--accent-dim', '--send-bg', '--send-text', '--primary-text'];
  watch([theme, font], () => {
    document.documentElement.dataset.theme = theme.value;
    document.documentElement.dataset.font = font.value;
  }, { immediate: true, flush: 'sync' });
  watch([customColors, customAccent, accent, palette], () => {
    const style = document.documentElement.style;
    colorTokens.forEach(token => style.removeProperty(token));
    style.removeProperty('color-scheme');
    const set = (token: string, value: string) => style.setProperty(token, value);
    if (customColors.value) {
      const p = palette.value;
      set('--bg', p.background); set('--bg-raised', p.surface); set('--bg-input', p.background);
      set('--composer-bg', p.surface); set('--composer-line', p.border); set('--line', p.border);
      set('--line-soft', `color-mix(in srgb, ${p.border} 60%, ${p.background})`);
      set('--text', p.text); set('--text-dim', `color-mix(in srgb, ${p.text} 78%, ${p.background})`);
      set('--text-faint', `color-mix(in srgb, ${p.text} 65%, ${p.background})`);
      set('--hover', `color-mix(in srgb, ${p.text} 8%, ${p.surface})`);
      set('--selected', `color-mix(in srgb, var(--accent) 16%, ${p.surface})`);
      set('color-scheme', luminance(p.background) > .4 ? 'light' : 'dark');
    }
    if (customAccent.value) {
      const foreground = contrast(accent.value, '#ffffff') >= contrast(accent.value, '#000000') ? '#ffffff' : '#000000';
      set('--accent', accent.value); set('--send-bg', accent.value); set('--send-text', foreground); set('--primary-text', foreground);
      set('--accent-dim', `color-mix(in srgb, ${accent.value} 65%, var(--bg))`);
      set('--selected', `color-mix(in srgb, ${accent.value} 16%, var(--bg-raised))`);
    }
  }, { immediate: true, deep: true, flush: 'sync' });
  watch([theme, font, customColors, customAccent, accent, palette, metrics], () => writeJSON(APPEARANCE_KEY, {
    theme: theme.value, font: font.value, customColors: customColors.value, customAccent: customAccent.value,
    accent: accent.value, palette: palette.value, metrics: metrics.value,
  }), { deep: true });
  function resetColors(): void {
    customColors.value = false; customAccent.value = false;
    accent.value = '#d6ad60'; palette.value = { ...DEFAULT_PALETTE };
  }
  return { metrics, theme, font, customColors, customAccent, accent, palette, paletteContrast, resetColors };
});
