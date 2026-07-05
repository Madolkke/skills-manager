<script setup lang="ts">
import { FilePlus2, Save } from "lucide-vue-next";
import BundleEditor from "../../../components/BundleEditor.vue";
import type { SkillBundleDraftFile, SkillBundleValidationResult } from "../../../lib/skillBundleDraft";

defineProps<{
  files: SkillBundleDraftFile[];
  validation: SkillBundleValidationResult;
  dirty: boolean;
  canSave: boolean;
  saving: boolean;
  windowed?: boolean;
}>();

const emit = defineEmits<{
  add: [];
  remove: [id: string];
  pathChange: [id: string, path: string];
  contentChange: [id: string, content: string];
  save: [];
}>();
</script>

<template>
  <section :class="['builder-workspace-panel', windowed && 'windowed']">
    <header class="builder-panel-head">
      <div v-if="!windowed">
        <span class="eyebrow">Workspace</span>
        <h2>工作区文件</h2>
        <p class="field-hint">Agent 在对话中写入的文本文件会显示在这里，你也可以直接编辑后继续对话。</p>
      </div>
      <div v-else class="builder-workspace-summary">
        <strong>{{ files.length }} 个文件</strong>
        <span>{{ dirty ? "有未保存修改" : "工作区已同步" }}</span>
      </div>
      <div class="builder-workspace-actions">
        <button class="secondary-button" type="button" @click="emit('add')">
          <FilePlus2 :size="16" />
          添加文件
        </button>
        <button class="secondary-button" type="button" :disabled="!canSave" @click="emit('save')">
          <Save :size="16" />
          {{ saving ? "保存中..." : dirty ? "保存工作区" : "已保存" }}
        </button>
      </div>
    </header>
    <div v-if="validation.globalErrors.length" class="form-error">{{ validation.globalErrors[0] }}</div>
    <BundleEditor
      :files="files"
      :validation="validation"
      root-label="workspace"
      @add="emit('add')"
      @remove="emit('remove', $event)"
      @path-change="(id, path) => emit('pathChange', id, path)"
      @content-change="(id, content) => emit('contentChange', id, content)"
    />
  </section>
</template>
