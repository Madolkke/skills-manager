<script setup lang="ts">
import { computed } from "vue";
import { Flag, Trash2 } from "lucide-vue-next";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowBundle, WorkflowConclusion, WorkflowValidationIssue } from "../../../types";
import WorkflowPredecessors from "./WorkflowPredecessors.vue";
import WorkflowTemplateEditor from "./WorkflowTemplateEditor.vue";
import { workflowConclusionExpressionVariables } from "../workflowExpressionVariables";
import { scanWorkflowTemplate } from "../workflowTemplate";
const props = defineProps<{ conclusion: WorkflowConclusion; bundle: WorkflowBundle; readonly: boolean; issues?: WorkflowValidationIssue[] }>();
const emit = defineEmits<{ change: [patch: Partial<WorkflowConclusion>]; remove: []; "predecessor-open": [id: string] }>();
const variables = computed(() => workflowConclusionExpressionVariables(props.bundle, props.conclusion.id));
const rootCauseDiagnostics = computed(() => diagnosticsFor("rootCause", props.conclusion.rootCause));
const repairDiagnostics = computed(() => diagnosticsFor("repairRecommendation", props.conclusion.repairRecommendation));
const severityLabels = { info: "信息", warning: "警告", error: "错误", critical: "严重" } as const;
function diagnosticsFor(field: "rootCause" | "repairRecommendation", value: string) {
  return [
    ...scanWorkflowTemplate(value),
    ...(props.issues ?? []).filter((item) => item.selection.type === "conclusion" && item.selection.id === props.conclusion.id && item.selection.field === field).map((item) => ({ code: item.code, message: item.message, start: 0, end: value.length, severity: item.severity })),
  ];
}
</script>

<template>
  <section class="workflow-document workflow-conclusion-document">
    <header class="workflow-document-head"><span><Flag :size="18" /></span><div><small>排查结论</small><h2>{{ props.conclusion.name }}</h2><p>结论是流程终点，描述根因和修复建议。</p></div><UiIconButton label="删除结论" variant="danger" :disabled="props.readonly" @click="emit('remove')"><Trash2 /></UiIconButton></header>
    <div class="workflow-form-grid"><label class="field-label"><span>结论名称</span><input :value="props.conclusion.name" :disabled="props.readonly" @input="emit('change', { name: ($event.target as HTMLInputElement).value })" /></label><label class="field-label"><span>严重等级</span><select :value="props.conclusion.severity || 'info'" :disabled="props.readonly" @change="emit('change', { severity: ($event.target as HTMLSelectElement).value as WorkflowConclusion['severity'] })"><option v-for="(label, value) in severityLabels" :key="value" :value="value">{{ label }}</option></select></label><label class="field-label span-2"><span>故障根因</span><WorkflowTemplateEditor :value="props.conclusion.rootCause" :variables="variables" :diagnostics="rootCauseDiagnostics" :readonly="props.readonly" aria-label="故障根因模板" @change="emit('change', { rootCause: $event })" /></label><label class="field-label span-2"><span>修复建议</span><WorkflowTemplateEditor :value="props.conclusion.repairRecommendation" :variables="variables" :diagnostics="repairDiagnostics" :readonly="props.readonly" aria-label="修复建议模板" @change="emit('change', { repairRecommendation: $event })" /></label></div>
    <WorkflowPredecessors :bundle="props.bundle" :target-id="props.conclusion.id" @open="emit('predecessor-open', $event)" />
  </section>
</template>
