<script setup lang="ts">
import { ArrowUpRight, ChevronDown, ChevronUp, Trash2 } from "lucide-vue-next";
import { computed, nextTick, ref } from "vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowBundle, WorkflowExpressionDiagnostic, WorkflowStep, WorkflowValidationIssue } from "../../../types";
import type { WorkflowPathTargetChoice } from "../workflowPathEditing";
import { workflowExpressionValidationKey } from "../useWorkflowExpressionValidation";
import { workflowExpressionVariables } from "../workflowExpressionVariables";
import WorkflowExpressionEditor from "./WorkflowExpressionEditor.vue";
import WorkflowTemplateEditor from "./WorkflowTemplateEditor.vue";
import WorkflowPathTargetPicker from "./WorkflowPathTargetPicker.vue";
import { scanWorkflowTemplate } from "../workflowTemplate";

const props = defineProps<{
  step: WorkflowStep;
  bundle: WorkflowBundle;
  diagnostics: Record<string, WorkflowExpressionDiagnostic[]>;
  issues: WorkflowValidationIssue[];
  readonly: boolean;
  sectionNumber: string;
}>();
const emit = defineEmits<{
  add: [choice: WorkflowPathTargetChoice];
  retarget: [id: string, choice: WorkflowPathTargetChoice];
  change: [id: string, patch: Record<string, unknown>];
  remove: [id: string];
  move: [id: string, direction: -1 | 1];
  "open-target": [id: string];
}>();
const root = ref<HTMLElement | null>(null);
const expressionVariables = computed(() => workflowExpressionVariables(props.bundle, props.step.id));

async function add(choice: WorkflowPathTargetChoice): Promise<void> {
  emit("add", choice);
  await nextTick();
  const pathId = props.step.topology.at(-1)?.id;
  if (!pathId) return;
  const card = root.value?.querySelector<HTMLElement>(`[data-path-id="${CSS.escape(pathId)}"]`);
  card?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  card?.querySelector<HTMLElement>("[data-path-condition] .cm-content")?.focus();
}

function conditionTextDiagnostics(transitionId: string, value: string) {
  const scanned = scanWorkflowTemplate(value);
  const diagnostics = [
    ...scanned,
    ...props.issues
      .filter((item) => item.selection.type === "step" && item.selection.id === props.step.id && item.selection.itemId === transitionId && item.selection.field === "conditionText")
      .filter((item) => !scanned.some((diagnostic) => diagnostic.code === item.code && diagnostic.message === item.message))
      .map((item) => ({ code: item.code, message: item.message, start: 0, end: value.length, severity: item.severity })),
  ];
  return diagnostics;
}
</script>

<template>
  <section ref="root" class="workflow-step-section">
    <div class="workflow-subhead">
      <div class="workflow-section-title"><span>{{ props.sectionNumber }}</span><div><h3>跳转到节点</h3><p>按作者顺序列出可能的跳转，不表达执行优先级。</p></div></div>
      <WorkflowPathTargetPicker :bundle="props.bundle" :source-step-id="props.step.id" variant="add" :readonly="props.readonly" @select="add" />
    </div>
    <article v-for="(item, index) in props.step.topology" :key="item.id" :data-path-id="item.id" class="workflow-transition-card">
      <div class="workflow-transition-order"><UiIconButton label="上移路径" size="sm" :disabled="props.readonly || index === 0" @click="emit('move', item.id, -1)"><ChevronUp /></UiIconButton><UiIconButton label="下移路径" size="sm" :disabled="props.readonly || index === props.step.topology.length - 1" @click="emit('move', item.id, 1)"><ChevronDown /></UiIconButton></div>
      <div class="workflow-form-grid compact-grid">
        <div class="field-label span-2"><span>目标节点</span><div class="workflow-path-target-row"><WorkflowPathTargetPicker :bundle="props.bundle" :source-step-id="props.step.id" :current-target-id="item.target.id" variant="target" :readonly="props.readonly" @select="emit('retarget', item.id, $event)" /><UiIconButton label="打开目标节点" @click="emit('open-target', item.target.id)"><ArrowUpRight /></UiIconButton></div></div>
        <div class="field-label span-2"><span>条件说明</span><WorkflowTemplateEditor data-path-condition :value="item.conditionText" :variables="expressionVariables" :diagnostics="conditionTextDiagnostics(item.id, item.conditionText)" :readonly="props.readonly" placeholder="留空表示无条件跳转；可使用模板表达式" aria-label="条件说明" @change="emit('change', item.id, { conditionText: $event })" /></div>
        <div class="field-label span-2"><span>条件表达式</span><WorkflowExpressionEditor :value="item.conditionExpression" :variables="expressionVariables" :diagnostics="props.diagnostics[workflowExpressionValidationKey(props.step.id, item.id)] ?? []" :readonly="props.readonly" @change="emit('change', item.id, { conditionExpression: $event })" /></div>
      </div>
      <UiIconButton label="删除路径" size="sm" variant="danger" :disabled="props.readonly" @click="emit('remove', item.id)"><Trash2 /></UiIconButton>
    </article>
    <div v-if="props.step.topology.length === 0" class="workflow-empty workflow-transition-empty">尚未声明跳转，可连接已有节点或直接创建下一步。</div>
  </section>
</template>
