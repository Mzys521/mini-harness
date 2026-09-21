import { defineStore } from 'pinia';
import { ref, watch } from 'vue';
import { readJSON, writeJSON } from '@/api/storage';

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

export const useAppearance = defineStore('appearance', () => {
  const saved = readJSON<{ theme?: Theme; font?: Font }>(APPEARANCE_KEY);
  const theme = ref<Theme>(themes.some(item => item.value === saved?.theme) ? saved!.theme! : 'dark');
  const font = ref<Font>(fonts.some(item => item.value === saved?.font) ? saved!.font! : 'serif');
  watch([theme, font], () => {
    document.documentElement.dataset.theme = theme.value;
    document.documentElement.dataset.font = font.value;
  }, { immediate: true, flush: 'sync' });
  watch([theme, font], () => writeJSON(APPEARANCE_KEY, { theme: theme.value, font: font.value }));
  return { theme, font };
});
