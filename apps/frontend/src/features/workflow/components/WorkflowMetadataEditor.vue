<script setup lang="ts">
import { FileText } from "lucide-vue-next";
import type { SkillTagPayload, TagGroup, WorkflowMetadata } from "../../../types";
import WorkflowSkillTagsSection from "./WorkflowSkillTagsSection.vue";

const props = withDefaults(defineProps<{
  metadata: WorkflowMetadata;
  readonly: boolean;
  tags?: SkillTagPayload[];
  tagGroups?: TagGroup[];
  tagBusy?: boolean;
  tagError?: string;
}>(), { tags: () => [], tagGroups: () => [], tagBusy: false, tagError: "" });
const emit = defineEmits<{
  change: [patch: Partial<WorkflowMetadata>];
  "tag-change": [tags: SkillTagPayload[]];
  "tag-save": [tags: SkillTagPayload[]];
}>();
function versions(value: string): string[] {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}
</script>

<template>
  <section class="workflow-document">
    <header class="workflow-document-head"><span><FileText :size="18" /></span><div><small>WORKFLOW PROFILE</small><h2>基础信息</h2><p>名称和说明会进入同步生成的 SKILL.md。</p></div></header>
    <div class="workflow-form-grid">
      <label class="field-label span-2"><span>工作流名称</span><input :value="props.metadata.name" :disabled="props.readonly" @input="emit('change', { name: ($event.target as HTMLInputElement).value })" /></label>
      <label class="field-label"><span>工作流编码</span><input :value="props.metadata.code" :disabled="props.readonly" @input="emit('change', { code: ($event.target as HTMLInputElement).value })" /></label>
      <label class="field-label"><span>产业</span><input :value="props.metadata.industry" :disabled="props.readonly" @input="emit('change', { industry: ($event.target as HTMLInputElement).value })" /></label>
      <label class="field-label"><span>设备</span><input :value="props.metadata.device" :disabled="props.readonly" @input="emit('change', { device: ($event.target as HTMLInputElement).value })" /></label>
      <label class="field-label"><span>适用版本</span><input :value="props.metadata.versions.join(', ')" :disabled="props.readonly" placeholder="V8R22, V8R23" @change="emit('change', { versions: versions(($event.target as HTMLInputElement).value) })" /></label>
      <label class="field-label span-2"><span>工作流说明</span><textarea rows="7" :value="props.metadata.description" :disabled="props.readonly" @input="emit('change', { description: ($event.target as HTMLTextAreaElement).value })" /></label>
      <label class="field-label span-2"><span>问题现象</span><textarea aria-label="问题现象" rows="5" :value="props.metadata.symptom" :disabled="props.readonly" placeholder="描述告警、用户感知或触发条件（可选）" @input="emit('change', { symptom: ($event.target as HTMLTextAreaElement).value })" /></label>
    </div>
    <WorkflowSkillTagsSection :tags="props.tags" :groups="props.tagGroups" :disabled="props.readonly || props.tagBusy" :error="props.tagError" @change="emit('tag-change', $event)" @save="emit('tag-save', $event)" />
  </section>
</template>
