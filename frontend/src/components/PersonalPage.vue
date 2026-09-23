<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { request } from '@/api/client';
import { chatHref } from '@/composables/useWorkbenchRoute';
import { useChat } from '@/stores/chat';
import AppIcon from './AppIcon.vue';

const props = defineProps<{ page: 'skills' | 'automations' | 'preferences' }>();
const emit = defineEmits<{ open: [href: string] }>();
const chat = useChat();
interface Skill { id: string; name: string; description: string; instructions: string; enabled: boolean | number }
interface Schedule { id: string; name: string; prompt: string; enabled: boolean | number; next_run: string; interval_seconds: number; last_status: string; last_error: string; run_status?: string; last_session_id: string; workspace_id: string }
const title = computed(() => ({skills:'技能',automations:'定时任务',preferences:'使用习惯'}[props.page]));
const loading = ref(false), busy = ref(false), error = ref(''), notice = ref('');
const preferencesLoaded = ref(false);
const skills = ref<Skill[]>([]), tasks = ref<Schedule[]>([]), preferences = ref('');
const editing = ref(false), editingId = ref(''), confirmId = ref('');
const name = ref(''), description = ref(''), instructions = ref(''), enabled = ref(true);
const prompt = ref(''), runAt = ref(''), interval = ref(0), workspace = ref('');
const selectedSkills = ref<string[]>([]);
const statuses: Record<string,string> = {pending:'等待首次执行',submitted:'已提交',dispatching:'正在提交',failed:'提交失败',interrupted:'提交中断',completed:'已完成',running:'执行中',waiting:'等待批准',cancelled:'已取消',removed:'记录已删除'};
let version = 0;
async function load(): Promise<void> {
  const current = ++version; loading.value = true; error.value = ''; editing.value = false;
  try {
    if (props.page === 'preferences') { preferencesLoaded.value=false; const data = await request<{content:string}>('/v1/preferences'); if(current===version) { preferences.value=data.content; preferencesLoaded.value=true; } }
    else if (props.page === 'skills') { const data = await request<{items:Skill[]}>('/v1/skills'); if(current===version) skills.value=data.items; }
    else {
      const [data, available] = await Promise.all([request<{items:Schedule[]}>('/v1/automations'),request<{items:Skill[]}>('/v1/skills')]);
      if(current===version) { tasks.value=data.items; skills.value=available.items; }
    }
  } catch(caught) { if(current===version) error.value=(caught as Error).message; }
  finally { if(current===version) loading.value=false; }
}
async function mutate(action: () => Promise<unknown>, message: string): Promise<void> {
  busy.value=true; error.value=''; notice.value='';
  try { await action(); await load(); notice.value=message; } catch(caught) { error.value=(caught as Error).message; }
  finally { busy.value=false; }
}
function start(skill?: Skill): void {
  editingId.value=skill?.id??''; name.value=skill?.name??''; description.value=skill?.description??'';
  instructions.value=skill?.instructions??''; enabled.value=skill ? !!skill.enabled : true;
  prompt.value=''; runAt.value=''; interval.value=0; workspace.value=''; selectedSkills.value=[]; editing.value=true;
}
async function save(): Promise<void> {
  if(props.page==='skills') await mutate(()=>request(`/v1/skills${editingId.value ? `/${encodeURIComponent(editingId.value)}` : ''}`, {method:editingId.value?'PUT':'POST',body:JSON.stringify({name:name.value,description:description.value,instructions:instructions.value,enabled:enabled.value})}),'技能已保存');
  else if(props.page==='automations') {
    const date = new Date(runAt.value);
    if(!Number.isFinite(date.getTime()) || date.getTime()<=Date.now()) { error.value='请选择未来的执行时间'; return; }
    await mutate(()=>request('/v1/automations',{method:'POST',body:JSON.stringify({name:name.value,prompt:prompt.value,run_at:date.toISOString(),interval_seconds:Number(interval.value),workspace_id:workspace.value||null,skill_ids:selectedSkills.value})}),'定时任务已创建');
  } else await mutate(()=>request('/v1/preferences',{method:'PUT',body:JSON.stringify({content:preferences.value})}),'使用习惯已保存，下次发送消息时生效');
}
async function importSkill(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement, file=input.files?.[0];
  if(!file) return;
  if(file.size>80000) {error.value='SKILL.md 文件过大';input.value='';return;}
  const document=await file.text();
  await mutate(()=>request('/v1/skills/import',{method:'POST',body:JSON.stringify({document})}),'SKILL.md 已导入');
  input.value='';
}
async function toggle(item: Skill | Schedule): Promise<void> {
  if(props.page==='skills') { const skill=item as Skill; await mutate(()=>request(`/v1/skills/${encodeURIComponent(item.id)}`,{method:'PUT',body:JSON.stringify({name:skill.name,description:skill.description,instructions:skill.instructions,enabled:!skill.enabled})}),'技能状态已更新'); }
  else await mutate(()=>request(`/v1/automations/${encodeURIComponent(item.id)}`,{method:'PATCH',body:JSON.stringify({enabled:!item.enabled})}),'任务状态已更新');
}
async function remove(): Promise<void> {
  const id=confirmId.value;
  await mutate(()=>request(`/v1/${props.page}/${encodeURIComponent(id)}`,{method:'DELETE'}),'已删除');
  if(!error.value) confirmId.value='';
}
watch(()=>props.page,()=>{confirmId.value='';notice.value='';void load();},{immediate:true});
onUnmounted(()=>{version++;});
</script>

<template>
  <section class="route-page personal-page">
    <header class="page-heading"><div class="page-symbol"><AppIcon :name="page==='automations'?'clock':page==='skills'?'skill':'settings'" /></div><div><small>MINI HARNESS</small><h1>{{ title }}</h1></div></header>
    <p class="hint" v-if="page==='automations'">本地服务运行时自动执行，重新启动后只补执行一次。也可在对话中要求创建任务，批准后生效；写文件等操作仍需批准。</p>
    <p class="hint" v-else-if="page==='skills'">创建个人指令技能，或导入带 name / description 元数据的 SKILL.md；在对话输入区选择使用。仅导入指令正文，不运行脚本或加载附带文件。</p>
    <p class="hint" v-else>所有项目、普通对话和临时对话都会读取这里的习惯。你也可以在普通或项目对话中要求“记住我的偏好”，批准后保存；临时对话不会更新这些内容。</p>
    <div class="page-toolbar"><button type="button" :disabled="loading||busy" @click="load">刷新</button><button v-if="page!=='preferences'" type="button" class="primary" :disabled="busy||loading" @click="start()">{{ page==='skills'?'创建技能':'创建定时任务' }}</button><label v-if="page==='skills'" class="file-button">导入 SKILL.md<input type="file" accept=".md,text/markdown" :disabled="busy" @change="importSkill" /></label></div>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" class="hint" role="status">{{ notice }}</p><p v-if="loading" class="hint">正在加载…</p>
    <form v-if="page==='preferences'&&!loading&&preferencesLoaded" class="capability-card editor-form" @submit.prevent="save"><label class="field"><span>使用习惯与长期偏好</span><textarea v-model="preferences" rows="10" maxlength="4000" placeholder="例如：请默认使用中文；回答简洁；先给结论，再解释。" /></label><button class="primary" :disabled="busy">保存习惯</button></form>
    <form v-if="editing" class="capability-card editor-form" @submit.prevent="save">
      <h2>{{ editingId?'编辑技能':page==='skills'?'新建技能':'新建定时任务' }}</h2>
      <label class="field"><span>名称</span><input v-model="name" required maxlength="120" /></label>
      <template v-if="page==='skills'"><label class="field"><span>描述</span><input v-model="description" maxlength="2000" /></label><label class="field"><span>Markdown 指令</span><textarea v-model="instructions" required rows="8" maxlength="16000" /></label><label class="checkbox"><input type="checkbox" v-model="enabled" />启用技能</label></template>
      <template v-else><label class="field"><span>任务指令</span><textarea v-model="prompt" required rows="4" maxlength="16000" /></label><div class="form-columns"><label class="field"><span>首次执行时间（本机时区）</span><input type="datetime-local" v-model="runAt" required /></label><label class="field"><span>重复</span><select v-model="interval"><option :value="0">仅一次</option><option :value="3600">每小时</option><option :value="86400">每 24 小时</option><option :value="604800">每 7 天</option></select></label></div><label class="field"><span>执行位置</span><select v-model="workspace"><option value="">普通对话（无工作区）</option><option v-for="item in chat.workspaces" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><fieldset v-if="skills.some(item=>item.enabled)" class="skill-options"><legend>使用技能</legend><label v-for="skill in skills.filter(item=>item.enabled)" :key="skill.id" class="checkbox"><input v-model="selectedSkills" type="checkbox" :value="skill.id" />{{ skill.name }}</label></fieldset></template>
      <footer class="page-toolbar"><button type="submit" class="primary" :disabled="busy">保存</button><button type="button" :disabled="busy" @click="editing=false">取消</button></footer>
    </form>
    <template v-if="page==='skills'&&!loading"><p v-if="!skills.length" class="page-empty">还没有技能，创建或导入第一个 SKILL.md。</p><article v-for="skill in skills" :key="skill.id" class="capability-card"><header><h2>{{ skill.name }}</h2><span class="capability-badge">{{ skill.enabled?'已启用':'已停用' }}</span></header><p>{{ skill.description }}</p><details><summary>查看指令</summary><pre class="skill-source">{{ skill.instructions }}</pre></details><footer class="page-toolbar"><button :disabled="busy" @click="start(skill)">编辑</button><button :disabled="busy" @click="toggle(skill)">{{ skill.enabled?'停用':'启用' }}</button><button :disabled="busy" @click="confirmId=skill.id">删除</button></footer></article></template>
    <template v-if="page==='automations'&&!loading"><p v-if="!tasks.length" class="page-empty">还没有定时任务。</p><article v-for="task in tasks" :key="task.id" class="capability-card"><header><h2>{{ task.name }}</h2><span class="capability-badge">{{ task.enabled?'已启用':'已停用 / 单次已触发' }}</span></header><p>{{ task.prompt }}</p><p class="hint">{{ task.interval_seconds ? `每 ${task.interval_seconds/3600} 小时` : '仅一次' }} · {{ task.enabled?'下次执行':'计划时间' }} {{ new Date(task.next_run).toLocaleString() }}</p><p class="hint">{{ statuses[task.run_status??task.last_status]??task.last_status }}</p><p v-if="task.last_error" class="error">{{ task.last_error }}</p><footer class="page-toolbar"><button :disabled="busy" @click="toggle(task)">{{ task.enabled?'暂停':'启用' }}</button><a v-if="task.last_session_id" :href="chatHref(task.workspace_id??'',task.last_session_id)" @click.prevent="emit('open',chatHref(task.workspace_id??'',task.last_session_id))">查看执行对话</a><button :disabled="busy" @click="confirmId=task.id">删除</button></footer></article></template>
    <div v-if="confirmId" class="overlay" @click.self="confirmId=''"><section class="creator confirm"><h2>确认删除</h2><p>{{ page==='skills'?'删除此技能后，使用它的定时任务需要重新创建。':'删除定时任务会停止后续调度，已生成的对话仍保留。' }}</p><footer><button :disabled="busy" @click="confirmId=''">取消</button><button class="danger-solid" :disabled="busy" @click="remove">确认删除</button></footer></section></div>
  </section>
</template>
