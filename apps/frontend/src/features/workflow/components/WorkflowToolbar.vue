<script setup lang="ts">
import { AlertTriangle, ArrowLeft, Check, LockKeyhole, Redo2, RefreshCw, RotateCcw, Save, Undo2 } from "lucide-vue-next";
import { computed } from "vue";
import UiButton from "../../../components/ui/UiButton.vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { UiButtonState } from "../../../components/ui/button";

const props = defineProps<{
  title: string;
  revision?: number;
  syncLabel?: string;
  lastSavedAt?: string;
  dirty: boolean;
  readonly: boolean;
  saveState: UiButtonState;
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

const lastSavedLabel = computed(() => {
  if (!props.lastSavedAt) return "尚未保存";
  const date = new Date(props.lastSavedAt);
  return Number.isNaN(date.getTime()) ? props.lastSavedAt : date.toLocaleString();
});
</script>

<template>
  <header class="workflow-toolbar">
    <div class="workflow-toolbar-context">
      <UiIconButton label="返回 Skill" variant="secondary" @click="emit('back')"><ArrowLeft /></UiIconButton>
      <div class="workflow-toolbar-title">
        <span>Workflow editor</span>
        <strong :title="props.title">{{ props.title }}</strong>
      </div>
      <span v-if="props.revision" class="workflow-toolbar-revision">r{{ props.revision }}</span>
      <span v-if="props.syncLabel" class="workflow-toolbar-sync">{{ props.syncLabel }}</span>
      <span v-if="props.readonly" class="workflow-toolbar-readonly"><LockKeyhole />只读</span>
    </div>

    <div class="workflow-toolbar-persistence" role="status" aria-live="polite">
      <span class="workflow-toolbar-updated">最后保存 <time :datetime="props.lastSavedAt">{{ lastSavedLabel }}</time></span>
      <div :class="['workflow-save-state', props.dirty && 'dirty']">
        <Transition name="workflow-state-swap" mode="out-in">
          <span :key="props.dirty ? 'dirty' : 'saved'">
            <AlertTriangle v-if="props.dirty" /><Check v-else />
            {{ props.dirty ? "修改尚未写入服务端" : "内容已写入服务端" }}
          </span>
        </Transition>
      </div>
    </div>

    <div class="workflow-toolbar-spacer" />
    <div class="workflow-toolbar-actions workflow-toolbar-tools">
      <UiIconButton label="撤销" tooltip="撤销 (Ctrl+Z)" variant="ghost" :disabled="!props.canUndo" disabled-reason="暂无可撤销操作" @click="emit('undo')"><Undo2 /></UiIconButton>
      <UiIconButton label="重做" tooltip="重做 (Ctrl+Shift+Z)" variant="ghost" :disabled="!props.canRedo" disabled-reason="暂无可重做操作" @click="emit('redo')"><Redo2 /></UiIconButton>
      <UiIconButton label="放弃未保存修改" variant="ghost" :disabled="!props.dirty" disabled-reason="当前没有未保存修改" @click="emit('discard')"><RotateCcw /></UiIconButton>
    </div>

    <div class="workflow-toolbar-actions workflow-toolbar-commands">
      <UiButton variant="secondary" @click="emit('validation')">
        <template #icon><AlertTriangle /></template>
        校验 <Transition name="workflow-count"><span v-if="props.issueCount" class="workflow-count">{{ props.issueCount }}</span></Transition>
      </UiButton>
      <UiButton
        variant="primary"
        :state="props.saveState"
        :disabled="props.readonly || (!props.dirty && props.saveState !== 'success')"
        :disabled-reason="props.readonly ? '只读模式无法保存' : '当前没有未保存修改'"
        loading-label="保存中"
        success-label="已保存"
        title="保存 Workflow (Ctrl+S)"
        @click="emit('save')"
      >
        <template #icon><Save /></template>
        保存 Workflow
      </UiButton>
      <UiButton variant="secondary" :state="props.syncing ? 'loading' : 'idle'" :disabled="!props.canSync" :disabled-reason="props.dirty ? '请先保存 Workflow' : props.issueCount ? '请先解决校验问题' : '当前无法创建 Skill 版本'" loading-label="同步中" @click="emit('sync')">
        <template #icon><RefreshCw /></template>
        同步到 Skill
      </UiButton>
    </div>
  </header>
</template>
