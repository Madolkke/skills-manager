<script setup lang="ts">
import Modal from "../../../components/Modal.vue";
import type { SkillBundleDraftFile, SkillBundleValidationResult } from "../../../lib/skillBundleDraft";
import BuilderWorkspacePanel from "./BuilderWorkspacePanel.vue";

defineProps<{
  files: SkillBundleDraftFile[];
  validation: SkillBundleValidationResult;
  dirty: boolean;
  canSave: boolean;
  saving: boolean;
}>();

const emit = defineEmits<{
  close: [];
  add: [];
  remove: [id: string];
  pathChange: [id: string, path: string];
  contentChange: [id: string, content: string];
  save: [];
}>();
</script>

<template>
  <Modal title="工作区文件" description="查看、编辑 Agent 在本次会话中生成的文本文件。" size="workspace" @close="emit('close')">
    <div class="builder-workspace-modal">
      <BuilderWorkspacePanel
        :files="files"
        :validation="validation"
        :dirty="dirty"
        :can-save="canSave"
        :saving="saving"
        windowed
        @add="emit('add')"
        @remove="emit('remove', $event)"
        @path-change="(id, path) => emit('pathChange', id, path)"
        @content-change="(id, content) => emit('contentChange', id, content)"
        @save="emit('save')"
      />
    </div>
  </Modal>
</template>
