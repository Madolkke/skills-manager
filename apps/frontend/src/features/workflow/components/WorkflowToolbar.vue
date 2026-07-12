<script setup lang="ts">
import { AlertTriangle, ArrowLeft, Check, Redo2, RefreshCw, RotateCcw, Save, Undo2 } from "lucide-vue-next";

const props = defineProps<{
  title: string;
  revision?: number;
  syncLabel?: string;
  dirty: boolean;
  readonly: boolean;
  saving: boolean;
  syncing: boolean;
  issueCount: number;
  canUndo: boolean;
  canRedo: boolean;
  canSync: boolean;
}>();
const emit = defineEmits<{
  back: [];
  undo: [];
  redo: [];
  discard: [];
  save: [];
  sync: [];
  validation: [];
}>();
</script>

<template>
  <header class="workflow-toolbar">
    <div class="workflow-toolbar-context">
      <button class="icon-button" type="button" title="返回 Skill" aria-label="返回 Skill" @click="emit('back')"><ArrowLeft :size="18" /></button>
      <div class="workflow-toolbar-title">
        <span>Workflow editor</span>
        <strong :title="props.title">{{ props.title }}</strong>
      </div>
      <span v-if="props.revision" class="workflow-toolbar-revision">r{{ props.revision }}</span>
      <span v-if="props.syncLabel" class="workflow-toolbar-sync">{{ props.syncLabel }}</span>
    </div>

    <div :class="['workflow-save-state', props.dirty && 'dirty']">
      <AlertTriangle v-if="props.dirty" :size="14" /><Check v-else :size="14" />
      {{ props.dirty ? "未保存" : "已保存" }}
    </div>

    <div class="workflow-toolbar-spacer" />
    <div class="workflow-toolbar-actions workflow-toolbar-tools">
      <button class="icon-button" type="button" title="撤销 (Ctrl+Z)" aria-label="撤销" :disabled="!props.canUndo" @click="emit('undo')"><Undo2 :size="17" /></button>
      <button class="icon-button" type="button" title="重做 (Ctrl+Shift+Z)" aria-label="重做" :disabled="!props.canRedo" @click="emit('redo')"><Redo2 :size="17" /></button>
      <button class="icon-button" type="button" title="放弃未保存修改" aria-label="放弃未保存修改" :disabled="!props.dirty" @click="emit('discard')"><RotateCcw :size="17" /></button>
    </div>

    <div class="workflow-toolbar-actions workflow-toolbar-commands">
      <button class="secondary-button workflow-toolbar-command" type="button" @click="emit('validation')"><AlertTriangle :size="15" />校验 <span v-if="props.issueCount" class="workflow-count">{{ props.issueCount }}</span></button>
      <button class="primary-button workflow-toolbar-command" type="button" :disabled="props.readonly || !props.dirty || props.saving" title="保存 Workflow (Ctrl+S)" @click="emit('save')"><Save :size="15" />{{ props.saving ? "保存中" : "保存 Workflow" }}</button>
      <button class="secondary-button workflow-toolbar-command" type="button" :disabled="!props.canSync || props.syncing" @click="emit('sync')"><RefreshCw :size="15" />{{ props.syncing ? "同步中" : "同步到 Skill" }}</button>
    </div>
  </header>
</template>
