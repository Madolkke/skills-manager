<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { CollectionDefinition, WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import WorkflowGraph from "./WorkflowGraph.vue";
import WorkflowReadPreview from "./WorkflowReadPreview.vue";
import WorkflowCollectionPreview from "./WorkflowCollectionPreview.vue";

defineOptions({ inheritAttrs: false });

type PreviewTab = "graph" | "read" | "collections" | "validation";
const props = defineProps<{ bundle: WorkflowBundle; catalog: CollectionDefinition[]; issues: WorkflowValidationIssue[]; selection?: WorkflowSelection; initialTab?: PreviewTab }>();
const emit = defineEmits<{ select: [selection: WorkflowSelection]; navigate: [selection: WorkflowSelection]; toast: [message: string, tone?: "success" | "error"] }>();
const tab = defineModel<PreviewTab>("tab", { default: "graph" });
const expanded = defineModel<boolean>("expanded", { default: false });
const direction = ref<"DOWN" | "RIGHT">("RIGHT");
const previewPanel = ref<HTMLElement | null>(null);
let scrollingTimer: ReturnType<typeof setTimeout> | undefined;
const errorCount = computed(() => props.issues.filter((item) => item.severity === "error").length);
const warningCount = computed(() => props.issues.filter((item) => item.severity === "warning").length);

function showToast(message: string, tone?: "success" | "error"): void {
  emit("toast", message, tone);
}

function selectTab(next: PreviewTab): void {
  if (next !== "graph") expanded.value = false;
  tab.value = next;
}

function showScrollbarWhileScrolling(): void {
  previewPanel.value?.classList.add("is-scrolling");
  if (scrollingTimer) clearTimeout(scrollingTimer);
  scrollingTimer = setTimeout(() => previewPanel.value?.classList.remove("is-scrolling"), 700);
}

onMounted(() => previewPanel.value?.addEventListener("scroll", showScrollbarWhileScrolling, { passive: true }));
onBeforeUnmount(() => {
  if (scrollingTimer) clearTimeout(scrollingTimer);
  previewPanel.value?.removeEventListener("scroll", showScrollbarWhileScrolling);
});
</script>

<template>
  <section ref="previewPanel" v-bind="$attrs" class="workflow-preview-panel">
    <div :class="['workflow-preview-tabs', `is-${tab}`]" role="tablist" aria-label="Workflow 预览">
      <button v-for="item in [{ id: 'graph', label: '流程图' }, { id: 'read', label: '阅读视图' }, { id: 'collections', label: '采集视图' }, { id: 'validation', label: '校验' }]" :key="item.id" :class="tab === item.id && 'active'" type="button" role="tab" :aria-selected="tab === item.id" @click="selectTab(item.id as PreviewTab)">
        <span>{{ item.label }}</span><b v-if="item.id === 'validation' && props.issues.length" :class="errorCount ? 'has-errors' : 'has-warnings'">{{ props.issues.length }}</b>
      </button>
    </div>
    <Transition name="workflow-preview-switch" mode="out-in">
      <WorkflowGraph v-if="tab === 'graph'" key="graph" :bundle="props.bundle" :issues="props.issues" :selected="props.selection" :direction="direction" :compact="!expanded" allow-expand :expanded="expanded" @select="emit('select', $event)" @update:direction="direction = $event" @toggle-expand="expanded = !expanded" />
      <div v-else-if="tab === 'read'" key="read" class="workflow-preview-scroll"><WorkflowReadPreview :bundle="props.bundle" :catalog="props.catalog" @select="emit('select', $event)" /></div>
      <div v-else-if="tab === 'collections'" key="collections" class="workflow-preview-scroll"><WorkflowCollectionPreview :bundle="props.bundle" :catalog="props.catalog" @toast="showToast" /></div>
      <div v-else key="validation" class="workflow-validation-list"><div class="workflow-validation-summary"><strong :class="errorCount > 0 ? 'has-errors' : 'is-clear'">{{ errorCount }} 个错误</strong><span :class="warningCount > 0 && 'has-warnings'">{{ warningCount }} 个提醒</span></div><button v-for="issue in props.issues" :key="issue.id" :class="issue.severity" type="button" :aria-current="props.selection && issue.selection.type === props.selection.type && ('id' in issue.selection ? issue.selection.id : '') === ('id' in props.selection ? props.selection.id : '') && issue.selection.field === props.selection.field ? 'true' : undefined" @click="emit('navigate', issue.selection)"><strong>{{ issue.severity === "error" ? "错误" : "提醒" }}</strong><span>{{ issue.message }}</span></button><p v-if="props.issues.length === 0" class="workflow-empty">当前没有校验问题。</p></div>
    </Transition>
  </section>
</template>
