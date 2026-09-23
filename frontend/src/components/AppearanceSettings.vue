<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import AppIcon from '@/components/AppIcon.vue';
import PersonalPage from '@/components/PersonalPage.vue';
import { fonts, themes, metricOptions, paletteFields, isColor, useAppearance } from '@/stores/appearance';

const props = withDefaults(defineProps<{ initialSection?: 'appearance' | 'colors' | 'preferences' | 'metrics' }>(), { initialSection: 'appearance' });
const emit = defineEmits<{ close: [] }>();
const appearance = useAppearance();
const dialog = ref<HTMLDialogElement | null>(null);
const section = ref(props.initialSection);
const sections = [
  { id: 'appearance', label: '外观与字体', icon: 'settings' },
  { id: 'colors', label: '自定义配色', icon: 'palette' },
  { id: 'metrics', label: '对话指标', icon: 'gauge' },
  { id: 'preferences', label: '使用习惯', icon: 'thought' },
] as const;
const preferencesVisited = ref(false);
watch(section, value => { if (value === 'preferences') preferencesVisited.value = true; }, { immediate: true });
function updateColor(event: Event, key: typeof paletteFields[number]['key'] | 'accent'): void {
  const input = event.target as HTMLInputElement;
  if (!isColor(input.value)) { input.setCustomValidity('请输入六位十六进制颜色，例如 #D6AD60'); input.reportValidity(); return; }
  input.setCustomValidity('');
  if (key === 'accent') appearance.accent = input.value;
  else appearance.palette[key] = input.value;
}
onMounted(() => dialog.value?.showModal());
</script>

<template>
  <dialog ref="dialog" class="appearance-dialog" aria-labelledby="appearance-title" @close="emit('close')" @click="event => { if (event.target === dialog) dialog?.close(); }">
    <div class="settings-shell">
      <header class="settings-heading">
        <div><span class="settings-eyebrow">让工作区更像你</span><h2 id="appearance-title">设置</h2></div>
        <button type="button" class="settings-close ghost" aria-label="关闭设置" @click="dialog?.close()"><AppIcon name="close" /></button>
      </header>
      <nav class="settings-nav" aria-label="设置分类">
        <button v-for="item in sections" :key="item.id" type="button" :aria-current="section === item.id ? 'page' : undefined" @click="section = item.id"><AppIcon :name="item.icon" /><span>{{ item.label }}</span></button>
      </nav>
      <div class="settings-content">
      <section v-show="section === 'appearance'" class="appearance-content" aria-label="外观与字体">
      <h3>外观与字体</h3>
      <fieldset>
        <legend>页面主题</legend>
        <div class="theme-options">
          <label v-for="item in themes" :key="item.value" class="theme-option" :class="{ selected: appearance.theme === item.value }">
            <input v-model="appearance.theme" type="radio" name="theme" :value="item.value" />
            <span class="theme-swatch" :class="`swatch-${item.value}`"><i /><b /><em /></span>
            <span>{{ item.label }}</span><small>{{ item.note }}</small>
          </label>
        </div>
      </fieldset>
      <fieldset>
        <legend>页面字体</legend>
        <label v-for="item in fonts" :key="item.value" class="font-option" :class="{ selected: appearance.font === item.value }">
          <input v-model="appearance.font" type="radio" name="font" :value="item.value" />
          <span class="font-sample" :class="`font-${item.value}`">Aa 文</span>
          <span><strong>{{ item.label }}</strong><small>{{ item.note }}</small></span>
        </label>
      </fieldset>
      <div class="appearance-preview"><small>阅读预览</small><p>让想法落在纸上，让代码开始生长。</p><span>Make room for your next idea.</span><code>const idea = 'hello';</code></div>
      <footer>选择即时生效，自动保存在此浏览器。代码始终使用等宽字体。</footer>
      </section>
      <section v-show="section === 'colors'" class="appearance-content" aria-label="自定义配色">
        <h3>自定义配色</h3>
        <p class="hint">用自定义颜色覆盖主题，修改即时生效。关闭自定义即可恢复主题原色。</p>
        <fieldset class="color-settings">
          <legend>强调色</legend>
          <label class="checkbox"><input v-model="appearance.customAccent" type="checkbox" />自定义强调色</label>
          <div class="color-control" :class="{ inactive: !appearance.customAccent }"><span>按钮与选中状态</span><input type="color" :value="appearance.accent" :disabled="!appearance.customAccent" aria-label="强调色拾色器" @input="updateColor($event, 'accent')" /><input class="color-hex" :value="appearance.accent" :disabled="!appearance.customAccent" aria-label="强调色 HEX" spellcheck="false" maxlength="7" @input="($event.target as HTMLInputElement).setCustomValidity('')" @change="updateColor($event, 'accent')" /></div>
          <div class="accent-presets"><button v-for="color in ['#d6ad60', '#86b78a', '#7ca7e8', '#b798df', '#d88e9d', '#dc875b']" :key="color" type="button" :style="{ '--swatch': color }" :aria-label="`使用强调色 ${color}`" :aria-pressed="appearance.customAccent && appearance.accent === color" @click="appearance.customAccent = true; appearance.accent = color" /></div>
        </fieldset>
        <fieldset class="color-settings">
          <legend>页面配色</legend>
          <label class="checkbox"><input v-model="appearance.customColors" type="checkbox" />自定义页面配色</label>
          <div v-for="field in paletteFields" :key="field.key" class="color-control" :class="{ inactive: !appearance.customColors }"><span>{{ field.label }}</span><input type="color" :value="appearance.palette[field.key]" :disabled="!appearance.customColors" :aria-label="`${field.label}拾色器`" @input="updateColor($event, field.key)" /><input class="color-hex" :value="appearance.palette[field.key]" :disabled="!appearance.customColors" :aria-label="`${field.label} HEX`" spellcheck="false" maxlength="7" @input="($event.target as HTMLInputElement).setCustomValidity('')" @change="updateColor($event, field.key)" /></div>
        </fieldset>
        <p v-if="appearance.customColors && appearance.paletteContrast < 4.5" class="contrast-warning" role="status">正文与背景对比度较低（{{ appearance.paletteContrast.toFixed(1) }}:1），建议调整颜色以便阅读。</p>
        <div class="appearance-preview"><small>配色预览</small><p>你的工作区，你的色彩。</p><span>按钮文字会随强调色自动调整明暗。</span><div class="page-toolbar"><button type="button" class="primary">主要按钮</button><span class="color-selection-preview">选中状态</span></div></div>
        <button type="button" class="palette-reset" @click="appearance.resetColors">恢复主题配色</button>
        <footer>自定义配色优先于主题，保存在此浏览器；恢复配色不会改变字体和使用习惯。</footer>
      </section>
      <section v-show="section === 'metrics'" class="appearance-content" aria-label="对话指标">
        <h3>对话指标</h3>
        <p class="hint">选择输入框下方显示的指标，全部关闭即可隐藏指标栏。</p>
        <fieldset class="metric-options"><legend>显示内容</legend>
          <label v-for="item in metricOptions" :key="item.key" class="checkbox"><input v-model="appearance.metrics[item.key]" type="checkbox" /><AppIcon :name="item.icon" />{{ item.label }}</label>
        </fieldset>
        <footer>指标在模型请求结束后更新。缓存命中率、速度和 token 为最近一轮统计；上下文余量根据配置窗口与最近一次请求估算，不包含尚未发送的草稿。未报告的数据用 — 表示。</footer>
      </section>
      <div v-show="section === 'preferences'" class="settings-preferences"><PersonalPage v-if="preferencesVisited" page="preferences" /></div>
      </div>
    </div>
  </dialog>
</template>
