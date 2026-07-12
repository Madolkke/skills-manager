<script setup lang="ts">
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Braces,
  ChevronRight,
  FileText,
  Flag,
  GripVertical,
  Library,
  Play,
  Plus,
  Search,
  TerminalSquare,
} from "lucide-vue-next";
import { computed, ref } from "vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowBundle, WorkflowNode, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import { workflowConclusions, workflowSteps } from "../domain/utils";
import { useSortableList } from "../useSortableList";

const props = defineProps<{
  bundle: WorkflowBundle;
  selection: WorkflowSelection;
  issues: WorkflowValidationIssue[];
  readonly: boolean;
}>();
const emit = defineEmits<{
  select: [selection: WorkflowSelection];
  "add-step": [];
  "add-conclusion": [];
  move: [kind: "step" | "conclusion", id: string, direction: -1 | 1];
  reorder: [kind: "step" | "conclusion", ids: string[]];
}>();

const query = ref("");
const stepsOpen = ref(true);
const conclusionsOpen = ref(true);
const stepList = ref<HTMLElement | null>(null);
const conclusionList = ref<HTMLElement | null>(null);
const steps = computed(() => workflowSteps(props.bundle));
const conclusions = computed(() => workflowConclusions(props.bundle));
const filteredSteps = computed(() => filterNodes(steps.value));
const filteredConclusions = computed(() => filterNodes(conclusions.value));

useSortableList(stepList, {
  disabled: () => props.readonly || Boolean(query.value),
  onReorder: (ids) => emit("reorder", "step", ids),
});
useSortableList(conclusionList, {
  disabled: () => props.readonly || Boolean(query.value),
  onReorder: (ids) => emit("reorder", "conclusion", ids),
});

function filterNodes<T extends WorkflowNode>(items: T[]): T[] {
  const term = query.value.trim().toLocaleLowerCase();
  return term ? items.filter((item) => nodeSearchText(item).toLocaleLowerCase().includes(term)) : items;
}

function nodeSearchText(item: WorkflowNode): string {
  return "stepType" in item
    ? `${item.name} ${item.description}`
    : `${item.name} ${item.rootCause} ${item.repairRecommendation}`;
}

function active(type: WorkflowSelection["type"], id?: string): boolean {
  return props.selection.type === type && (!id || ("id" in props.selection && props.selection.id === id));
}

function issueCount(id: string): number {
  return props.issues.filter((issue) => {
    const selection = issue.selection;
    if ("id" in selection && selection.id === id) return true;
    if (selection.type !== "collection") return false;
    return steps.value.some((step) => step.id === id && step.collectionCalls.some((call) => call.definition.id === selection.id));
  }).length;
}
</script>

<template>
  <nav class="workflow-sidebar" aria-label="工作流结构">
    <div class="workflow-sidebar-search">
      <Search :size="14" />
      <input v-model="query" type="search" placeholder="搜索步骤或结论" aria-label="搜索工作流节点" />
    </div>

    <div class="workflow-sidebar-section workflow-sidebar-root">
      <span class="workflow-sidebar-label">工作流</span>
      <button :class="['workflow-sidebar-item', active('metadata') && 'active']" type="button" :aria-current="active('metadata') ? 'page' : undefined" @click="emit('select', { type: 'metadata' })"><FileText :size="15" /><span>基础信息</span></button>
      <button :class="['workflow-sidebar-item', (active('inputs') || active('roles')) && 'active']" type="button" :aria-current="active('inputs') || active('roles') ? 'page' : undefined" @click="emit('select', { type: 'inputs' })"><Braces :size="15" /><span>全局输入</span><small class="workflow-sidebar-dual-count">输入 {{ props.bundle.workflow.inputs.length }} · 角色 {{ props.bundle.workflow.deviceRoles.length }}</small></button>
      <button :class="['workflow-sidebar-item', active('collections') && 'active']" type="button" :aria-current="active('collections') ? 'page' : undefined" @click="emit('select', { type: 'collections' })"><Library :size="15" /><span>共享采集库</span></button>
    </div>

    <section class="workflow-sidebar-section">
      <div class="workflow-sidebar-heading">
        <button class="workflow-sidebar-toggle" type="button" :aria-expanded="stepsOpen" @click="stepsOpen = !stepsOpen">
          <ChevronRight :class="stepsOpen && 'open'" :size="14" />排查步骤 <small>{{ steps.length }}</small>
        </button>
        <UiIconButton label="添加步骤" size="sm" :disabled="props.readonly" @click="emit('add-step')"><Plus /></UiIconButton>
      </div>
      <Transition name="workflow-collapse">
        <div v-if="stepsOpen" ref="stepList" class="workflow-sidebar-node-list">
          <article v-for="(step, index) in filteredSteps" :key="step.id" :data-sort-id="step.id" :class="['workflow-sidebar-node', active('step', step.id) && 'active']">
            <button class="workflow-drag-handle" type="button" title="拖动排序" aria-label="拖动步骤排序" :disabled="props.readonly || Boolean(query)"><GripVertical :size="14" /></button>
            <button class="workflow-sidebar-node-main" type="button" :aria-current="active('step', step.id) ? 'page' : undefined" @click="emit('select', { type: 'step', id: step.id })">
              <span class="workflow-node-kind"><TerminalSquare :size="14" /></span>
              <span><strong>{{ step.name }}</strong><small>{{ step.description || "未填写说明" }}</small></span>
              <i v-if="step.isStart" title="起始步骤"><Play :size="10" /></i>
              <b v-if="issueCount(step.id)" class="workflow-node-issue"><AlertTriangle :size="10" />{{ issueCount(step.id) }}</b>
            </button>
            <div class="workflow-sidebar-node-actions">
              <UiIconButton label="上移步骤" size="sm" :disabled="props.readonly || index === 0 || Boolean(query)" @click="emit('move', 'step', step.id, -1)"><ArrowUp /></UiIconButton>
              <UiIconButton label="下移步骤" size="sm" :disabled="props.readonly || index === filteredSteps.length - 1 || Boolean(query)" @click="emit('move', 'step', step.id, 1)"><ArrowDown /></UiIconButton>
            </div>
          </article>
          <p v-if="filteredSteps.length === 0" class="workflow-sidebar-empty">没有匹配的步骤</p>
        </div>
      </Transition>
    </section>

    <section class="workflow-sidebar-section">
      <div class="workflow-sidebar-heading">
        <button class="workflow-sidebar-toggle" type="button" :aria-expanded="conclusionsOpen" @click="conclusionsOpen = !conclusionsOpen">
          <ChevronRight :class="conclusionsOpen && 'open'" :size="14" />排查结论 <small>{{ conclusions.length }}</small>
        </button>
        <UiIconButton label="添加结论" size="sm" :disabled="props.readonly" @click="emit('add-conclusion')"><Plus /></UiIconButton>
      </div>
      <Transition name="workflow-collapse">
        <div v-if="conclusionsOpen" ref="conclusionList" class="workflow-sidebar-node-list">
          <article v-for="(item, index) in filteredConclusions" :key="item.id" :data-sort-id="item.id" :class="['workflow-sidebar-node', active('conclusion', item.id) && 'active']">
            <button class="workflow-drag-handle" type="button" title="拖动排序" aria-label="拖动结论排序" :disabled="props.readonly || Boolean(query)"><GripVertical :size="14" /></button>
            <button class="workflow-sidebar-node-main" type="button" :aria-current="active('conclusion', item.id) ? 'page' : undefined" @click="emit('select', { type: 'conclusion', id: item.id })">
              <span class="workflow-node-kind conclusion"><Flag :size="14" /></span>
              <span><strong>{{ item.name }}</strong><small>{{ item.rootCause || "未填写故障根因" }}</small></span>
              <b v-if="issueCount(item.id)" class="workflow-node-issue"><AlertTriangle :size="10" />{{ issueCount(item.id) }}</b>
            </button>
            <div class="workflow-sidebar-node-actions">
              <UiIconButton label="上移结论" size="sm" :disabled="props.readonly || index === 0 || Boolean(query)" @click="emit('move', 'conclusion', item.id, -1)"><ArrowUp /></UiIconButton>
              <UiIconButton label="下移结论" size="sm" :disabled="props.readonly || index === filteredConclusions.length - 1 || Boolean(query)" @click="emit('move', 'conclusion', item.id, 1)"><ArrowDown /></UiIconButton>
            </div>
          </article>
          <p v-if="filteredConclusions.length === 0" class="workflow-sidebar-empty">没有匹配的结论</p>
        </div>
      </Transition>
    </section>
  </nav>
</template>
