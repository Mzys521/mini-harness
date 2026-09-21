<script setup lang="ts">
import { onMounted, ref } from 'vue';
import AppIcon from '@/components/AppIcon.vue';
import { fonts, themes, useAppearance } from '@/stores/appearance';

const emit = defineEmits<{ close: [] }>();
const appearance = useAppearance();
const dialog = ref<HTMLDialogElement | null>(null);
onMounted(() => dialog.value?.showModal());
</script>

<template>
  <dialog ref="dialog" class="appearance-dialog" aria-labelledby="appearance-title" @close="emit('close')" @click="event => { if (event.target === dialog) dialog?.close(); }">
    <div class="appearance-content">
      <header>
        <div><span class="settings-eyebrow">让工作区更像你</span><h2 id="appearance-title">外观设置</h2></div>
        <button type="button" class="settings-close ghost" aria-label="关闭设置" @click="dialog?.close()"><AppIcon name="close" /></button>
      </header>
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
    </div>
  </dialog>
</template>
