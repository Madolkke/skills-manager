<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { WorkflowBundle, WorkflowSelection } from "../../../types";
import { expandWorkflowExpressionVariable, workflowConclusionExpressionVariables, workflowExpressionVariables } from "../workflowExpressionVariables";
import { buildWorkflowExpressionVariableTree, workflowExpressionVariableDefaultExpanded } from "../workflowExpressionVariableTree";
import WorkflowExpressionVariableTreeNode from "./WorkflowExpressionVariableTreeNode.vue";

const props = defineProps<{ bundle: WorkflowBundle; selection?: WorkflowSelection }>();
const context = computed(() => {
  const selection = props.selection;
  if (selection?.type === "step") return { key: `step:${selection.id}`, label: nodeName(selection.id), variables: workflowExpressionVariables(props.bundle, selection.id) };
  if (selection?.type === "conclusion") return { key: `conclusion:${selection.id}`, label: nodeName(selection.id), variables: workflowConclusionExpressionVariables(props.bundle, selection.id) };
  return { key: "none", label: "", variables: [] };
});
const displayVariables = computed(() => context.value.variables.flatMap((variable) => (
  (variable.sampleCount ?? 1) > 1
    ? [variable, ...expandWorkflowExpressionVariable(variable, `${variable.reference}[0]`)]
    : [variable]
)));
const tree = computed(() => buildWorkflowExpressionVariableTree(displayVariables.value));
const expanded = ref<Set<string>>(new Set());
const hasContext = computed(() => context.value.key !== "none");

watch(() => context.value.key, () => { expanded.value = workflowExpressionVariableDefaultExpanded(tree.value); }, { immediate: true });

function nodeName(id: string): string {
  return props.bundle.workflow.nodes.find((node) => node.id === id)?.name || "未命名节点";
}

function toggle(reference: string): void {
  const next = new Set(expanded.value);
  if (next.has(reference)) next.delete(reference);
  else next.add(reference);
  expanded.value = next;
}
</script>

<template>
  <section class="workflow-expression-variables-panel" aria-label="可用变量">
    <header class="workflow-expression-variables-head">
      <div><strong>可用变量</strong><p v-if="hasContext">{{ context.label }} 的表达式环境</p><p v-else>选择步骤或结论后查看其表达式环境。</p></div>
      <span v-if="hasContext">{{ displayVariables.length }} 个路径</span>
    </header>
    <div v-if="!hasContext" class="workflow-empty">请先选择一个步骤或结论。</div>
    <div v-else-if="!tree.length" class="workflow-empty">当前节点没有可用变量。</div>
    <ul v-else class="workflow-variable-tree">
      <WorkflowExpressionVariableTreeNode v-for="node in tree" :key="node.id" :node="node" :expanded="expanded" @toggle="toggle" />
    </ul>
  </section>
</template>
