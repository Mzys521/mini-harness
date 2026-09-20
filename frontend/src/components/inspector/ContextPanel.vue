<script setup lang="ts">
import { computed } from "vue";

import IconBase from "@/components/common/IconBase.vue";
import { projectFiles } from "@/data/catalog";
import { useToastStore } from "@/stores/toast";
import { useWorkspaceStore } from "@/stores/workspace";

const workspace = useWorkspaceStore();
const toasts = useToastStore();

const selected = computed(
  () => projectFiles.find((file) => file.name === workspace.selectedFile) ?? projectFiles[0],
);
const lines = computed(() => selected.value.text.split("\n"));
const attached = computed(() => workspace.activeTask?.attachments ?? []);

function addSelected(): void {
  const task = workspace.activeTask;
  if (!task) return;
  const added = workspace.toggleAttachment(task, selected.value.name);
  toasts.push(added ? "已添加到下一条消息的上下文" : "已移除上下文");
}
</script>

<template>
  <div class="context-content">
    <div class="project-overview">
      <div class="overview-heading">
        <span class="repo-icon"><IconBase name="code" /></span>
        <div>
          <strong>mini-harness</strong>
          <span>A small core. A capable agent.</span>
        </div>
      </div>
      <div class="project-tags">
        <span><i class="python-dot" />Python</span>
        <span>11 个核心模块</span>
        <span>v0.11.0</span>
      </div>
    </div>

    <div class="file-section">
      <div class="section-label">
        <span>项目快照</span>
        <span class="read-only-label">只读</span>
      </div>
      <div class="file-tree">
        <button
          class="tree-folder"
          type="button"
          :aria-expanded="workspace.fileTreeOpen"
          @click="workspace.fileTreeOpen = !workspace.fileTreeOpen"
        >
          <IconBase :name="workspace.fileTreeOpen ? 'chevron-down' : 'chevron-right'" />
          <IconBase :name="workspace.fileTreeOpen ? 'folder-open' : 'folder'" />
          <span>mini-harness</span>
        </button>
        <div v-show="workspace.fileTreeOpen">
          <button
            v-for="file in projectFiles"
            :key="file.name"
            class="file-item"
            :class="{ active: file.name === workspace.selectedFile }"
            type="button"
            :title="file.name"
            @click="workspace.selectedFile = file.name"
          >
            <span class="file-icon" :class="{ doc: file.type === 'doc' }">
              <IconBase :name="file.type === 'python' ? 'code' : 'file'" />
            </span>
            <span>{{ file.name.split('/').pop() }}</span>
            <span class="file-caption">{{ file.caption }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="file-preview">
      <div class="file-preview-header">
        <span>{{ selected.name }}</span>
        <button
          class="icon-button small"
          type="button"
          :aria-label="attached.includes(selected.name) ? '从上下文移除此文件' : '添加此文件到上下文'"
          :title="attached.includes(selected.name) ? '从上下文移除' : '添加到上下文'"
          @click="addSelected"
        >
          <IconBase :name="attached.includes(selected.name) ? 'check' : 'plus'" />
        </button>
      </div>
      <pre tabindex="0" aria-label="文件快照预览"><span
        v-for="(line, index) in lines"
        :key="index"
        class="code-line"
      ><span class="code-number">{{ index + 1 }}</span>{{ line }}</span></pre>
    </div>

    <div class="context-note">
      <IconBase name="info" />
      <span>恰好的上下文，让每一步更有方向。</span>
    </div>
  </div>
</template>
