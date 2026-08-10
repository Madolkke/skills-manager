<script setup lang="ts">
import { computed, ref } from "vue";
import type { CollectionDefinition, WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import { useTransientScrollbar } from "../useTransientScrollbar";
import WorkflowAgentPanel from "../agent/components/WorkflowAgentPanel.vue";
import WorkflowGraph from "./WorkflowGraph.vue";
import WorkflowReadPreview from "./WorkflowReadPreview.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ bundle: WorkflowBundle; catalog: CollectionDefinition[]; issues: WorkflowValidationIssue[]; selection?: WorkflowSelection; initialTab?: PreviewTab; skillId?: string; revision?: number; dirty?: boolean; readonly?: boolean }>();
const emit = defineEmits<{ select: [selection: WorkflowSelection] }>();
type PreviewTab = "graph" | "read" | "validation" | "agent";
const tab = defineModel<PreviewTab>("tab", { default: "graph" });
const expanded = defineModel<boolean>("expanded", { default: false });
const direction = ref<"DOWN" | "RIGHT">("RIGHT");
const previewPanel = ref<HTMLElement | null>(null);
const errorCount = computed(() => props.issues.filter((item) => item.severity === "error").length);
const warningCount = computed(() => props.issues.filter((item) => item.severity === "warning").length);
useTransientScrollbar(previewPanel);

function selectTab(next: PreviewTab): void {
  if (next !== "graph") expanded.value = false;
  tab.value = next;
}

</script>

<template>
  <section ref="previewPanel" v-bind="$attrs" class="workflow-preview-panel">
    <div :class="['workflow-preview-tabs', `is-${tab}`]" role="tablist" aria-label="Workflow 预览">
      <button v-for="item in [{ id: 'graph', label: '流程图' }, { id: 'read', label: '阅读视图' }, { id: 'validation', label: '校验' }, { id: 'agent', label: '助手' }]" :key="item.id" :class="tab === item.id && 'active'" type="button" role="tab" :aria-selected="tab === item.id" @click="selectTab(item.id as PreviewTab)">
        <span>{{ item.label }}</span><b v-if="item.id === 'validation' && props.issues.length" :class="errorCount ? 'has-errors' : 'has-warnings'">{{ props.issues.length }}</b>
      </button>
    </div>
    <Transition name="workflow-preview-switch" mode="out-in">
      <WorkflowGraph v-if="tab === 'graph'" key="graph" :bundle="props.bundle" :issues="props.issues" :selected="props.selection" :direction="direction" :compact="!expanded" allow-expand :expanded="expanded" @select="emit('select', $event)" @update:direction="direction = $event" @toggle-expand="expanded = !expanded" />
      <div v-else-if="tab === 'read'" key="read" class="workflow-preview-scroll"><WorkflowReadPreview :bundle="props.bundle" :catalog="props.catalog" @select="emit('select', $event)" /></div>
      <div v-else-if="tab === 'validation'" key="validation" class="workflow-validation-list"><div class="workflow-validation-summary"><strong :class="errorCount > 0 ? 'has-errors' : 'is-clear'">{{ errorCount }} 个错误</strong><span :class="warningCount > 0 && 'has-warnings'">{{ warningCount }} 个提醒</span></div><button v-for="issue in props.issues" :key="issue.id" :class="issue.severity" type="button" @click="emit('select', issue.selection)"><strong>{{ issue.severity === "error" ? "错误" : "提醒" }}</strong><span>{{ issue.message }}</span></button><p v-if="props.issues.length === 0" class="workflow-empty">当前没有校验问题。</p></div>
      <WorkflowAgentPanel v-else-if="props.skillId && props.revision && props.selection" key="agent" :skill-id="props.skillId" :bundle="props.bundle" :revision="props.revision" :selection="props.selection" :dirty="Boolean(props.dirty)" :readonly="Boolean(props.readonly)" />
      <div v-else key="agent-unavailable" class="workflow-empty">助手上下文尚未就绪。</div>
    </Transition>
  </section>
</template>
