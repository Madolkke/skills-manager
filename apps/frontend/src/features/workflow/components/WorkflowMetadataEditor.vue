<script setup lang="ts">
import { FileText } from "lucide-vue-next";
import type { WorkflowMetadata } from "../../../types";

const props = defineProps<{ metadata: WorkflowMetadata; readonly: boolean }>();
const emit = defineEmits<{ change: [patch: Partial<WorkflowMetadata>] }>();
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
    </div>
  </section>
</template>
