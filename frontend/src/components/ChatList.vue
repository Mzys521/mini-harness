<script setup lang="ts">
import { ref } from 'vue';
import { useChat } from '@/stores/chat';
import { chatHref } from '@/composables/useWorkbenchRoute';
import AppIcon from './AppIcon.vue';
defineProps<{ active: boolean }>();
const emit=defineEmits<{open:[href:string];create:[];delete:[id:string,workspace:string]}>();
const chat=useChat(), archived=ref(false);
</script>
<template>
  <section class="side-section personal-chats" aria-label="普通对话">
    <header><span>对话</span><button class="icon" aria-label="新建普通对话" :disabled="chat.busy" @click="emit('create')"><AppIcon name="compose" /></button></header>
    <p v-if="chat.projectErrors['']" class="error">{{ chat.projectErrors[''] }}<button @click="chat.attempt(()=>chat.loadWorkspaceSessions(''))">重试</button></p>
    <ul class="session-list"><li v-for="item in chat.sessionGroups['']?.active??[]" :key="item.id" :class="{active:active&&chat.sessionId===item.id}"><a class="session-open" :href="chatHref('',item.id)" @click.prevent="emit('open',chatHref('',item.id))">{{ item.title }}</a><span class="session-actions"><button class="icon" :disabled="chat.busy" @click="chat.archiveSession(item.id,true,'')">归档</button><button class="icon danger" :disabled="chat.busy" @click="emit('delete',item.id,'')">删除</button></span></li></ul>
    <template v-if="chat.sessionGroups['']?.archived.length"><button class="archived-toggle" :aria-expanded="archived" @click="archived=!archived">{{ archived?'▾':'▸' }} 已归档 · {{ chat.sessionGroups['']?.archived.length }}</button><ul v-if="archived" class="session-list"><li v-for="item in chat.sessionGroups['']?.archived??[]" :key="item.id"><a class="session-open" :href="chatHref('',item.id)" @click.prevent="emit('open',chatHref('',item.id))">{{ item.title }}</a><span class="session-actions"><button class="icon" @click="chat.archiveSession(item.id,false,'')">恢复</button><button class="icon danger" @click="emit('delete',item.id,'')">删除</button></span></li></ul></template>
  </section>
</template>
