<script setup lang="ts">
import { ref } from "vue";
import type { CollectionDefinition, WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import WorkflowGraph from "./WorkflowGraph.vue";
import WorkflowReadPreview from "./WorkflowReadPreview.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ bundle: WorkflowBundle; catalog: CollectionDefinition[]; issues: WorkflowValidationIssue[]; selection?: WorkflowSelection; initialTab?: "graph" | "read" | "validation" }>();
const emit = defineEmits<{ select: [selection: WorkflowSelection] }>();
const tab = defineModel<"graph" | "read" | "validation">("tab", { default: "graph" });
const expanded = defineModel<boolean>("expanded", { default: false });
const direction = ref<"DOWN" | "RIGHT">("RIGHT");

function selectTab(next: "graph" | "read" | "validation"): void {
  if (next !== "graph") expanded.value = false;
  tab.value = next;
}
</script>

<template>
  <section v-bind="$attrs" class="workflow-preview-panel">
    <div :class="['workflow-preview-tabs', `is-${tab}`]" role="tablist" aria-label="Workflow 预览">
      <button v-for="item in [{ id: 'graph', label: '流程图' }, { id: 'read', label: '阅读视图' }, { id: 'validation', label: `校验 ${props.issues.length}` }]" :key="item.id" :class="tab === item.id && 'active'" type="button" role="tab" :aria-selected="tab === item.id" @click="selectTab(item.id as typeof tab)">{{ item.label }}</button>
    </div>
    <Transition name="workflow-preview-switch" mode="out-in">
      <WorkflowGraph v-if="tab === 'graph'" key="graph" :bundle="props.bundle" :issues="props.issues" :selected="props.selection" :direction="direction" :compact="!expanded" allow-expand :expanded="expanded" @select="emit('select', $event)" @update:direction="direction = $event" @toggle-expand="expanded = !expanded" />
      <div v-else-if="tab === 'read'" key="read" class="workflow-preview-scroll"><WorkflowReadPreview :bundle="props.bundle" :catalog="props.catalog" @select="emit('select', $event)" /></div>
      <div v-else key="validation" class="workflow-validation-list"><div class="workflow-validation-summary"><strong>{{ props.issues.filter((item) => item.severity === 'error').length }} 个错误</strong><span>{{ props.issues.filter((item) => item.severity === 'warning').length }} 个提醒</span></div><button v-for="issue in props.issues" :key="issue.id" :class="issue.severity" type="button" @click="emit('select', issue.selection)"><strong>{{ issue.severity === "error" ? "错误" : "提醒" }}</strong><span>{{ issue.message }}</span></button><p v-if="props.issues.length === 0" class="workflow-empty">当前没有校验问题。</p></div>
    </Transition>
  </section>
</template>
