<script setup lang="ts">
import { computed } from "vue";

import AppDialog from "@/components/common/AppDialog.vue";
import IconBase from "@/components/common/IconBase.vue";
import { projectFiles } from "@/data/catalog";
import { useUiStore } from "@/stores/ui";
import { useWorkspaceStore } from "@/stores/workspace";

const ui = useUiStore();
const workspace = useWorkspaceStore();

const attached = computed(() => workspace.activeTask?.attachments ?? []);

function toggle(name: string): void {
  const task = workspace.activeTask;
  if (task) workspace.toggleAttachment(task, name);
}
</script>

<template>
  <AppDialog v-model:open="ui.attachmentOpen" class-name="attachment-dialog" label-id="attachment-title">
    <div class="attachment-dialog-heading">
      <h2 id="attachment-title">添加项目上下文</h2>
      <button class="icon-button" type="button" aria-label="关闭上下文选择" @click="ui.closeAll()">
        <IconBase name="x" />
      </button>
    </div>
    <p>选择项目快照，随下一条消息一起发送。</p>
    <div>
      <button
        v-for="file in projectFiles"
        :key="file.name"
        class="attachment-option"
        type="button"
        :aria-pressed="attached.includes(file.name)"
        @click="toggle(file.name)"
      >
        <IconBase name="file" />
        <span>{{ file.name }}</span>
        <IconBase :name="attached.includes(file.name) ? 'check' : 'plus'" />
      </button>
    </div>
  </AppDialog>
</template>
