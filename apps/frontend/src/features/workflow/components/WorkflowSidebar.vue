<script setup lang="ts">
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Braces,
  ChevronDown,
  ChevronRight,
  FileText,
  Flag,
  GripVertical,
  Library,
  Play,
  Plus,
  Search,
  Server,
  TerminalSquare,
} from "lucide-vue-next";
import { computed, ref } from "vue";
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
      <button :class="['workflow-sidebar-item', active('metadata') && 'active']" type="button" @click="emit('select', { type: 'metadata' })"><FileText :size="15" /><span>基础信息</span></button>
      <button :class="['workflow-sidebar-item', active('inputs') && 'active']" type="button" @click="emit('select', { type: 'inputs' })"><Braces :size="15" /><span>全局输入</span><small>{{ props.bundle.workflow.inputs.length }}</small></button>
      <button :class="['workflow-sidebar-item', active('roles') && 'active']" type="button" @click="emit('select', { type: 'roles' })"><Server :size="15" /><span>设备角色</span><small>{{ props.bundle.workflow.deviceRoles.length }}</small></button>
      <button :class="['workflow-sidebar-item', active('collections') && 'active']" type="button" @click="emit('select', { type: 'collections' })"><Library :size="15" /><span>共享采集库</span></button>
    </div>

    <section class="workflow-sidebar-section">
      <div class="workflow-sidebar-heading">
        <button class="workflow-sidebar-toggle" type="button" @click="stepsOpen = !stepsOpen">
          <ChevronDown v-if="stepsOpen" :size="14" /><ChevronRight v-else :size="14" />排查步骤 <small>{{ steps.length }}</small>
        </button>
        <button class="workflow-sidebar-add" type="button" title="添加步骤" aria-label="添加步骤" :disabled="props.readonly" @click="emit('add-step')"><Plus :size="15" /></button>
      </div>
      <div v-if="stepsOpen" ref="stepList" class="workflow-sidebar-node-list">
        <article v-for="(step, index) in filteredSteps" :key="step.id" :data-sort-id="step.id" :class="['workflow-sidebar-node', active('step', step.id) && 'active']">
          <button class="workflow-drag-handle" type="button" title="拖动排序" aria-label="拖动步骤排序" :disabled="props.readonly || Boolean(query)"><GripVertical :size="14" /></button>
          <button class="workflow-sidebar-node-main" type="button" @click="emit('select', { type: 'step', id: step.id })">
            <span class="workflow-node-kind"><TerminalSquare :size="14" /></span>
            <span><strong>{{ step.name }}</strong><small>{{ step.description || "未填写说明" }}</small></span>
            <i v-if="step.isStart" title="起始步骤"><Play :size="10" /></i>
            <b v-if="issueCount(step.id)" class="workflow-node-issue"><AlertTriangle :size="10" />{{ issueCount(step.id) }}</b>
          </button>
          <div class="workflow-sidebar-node-actions">
            <button type="button" title="上移" aria-label="上移步骤" :disabled="props.readonly || index === 0 || Boolean(query)" @click="emit('move', 'step', step.id, -1)"><ArrowUp :size="12" /></button>
            <button type="button" title="下移" aria-label="下移步骤" :disabled="props.readonly || index === filteredSteps.length - 1 || Boolean(query)" @click="emit('move', 'step', step.id, 1)"><ArrowDown :size="12" /></button>
          </div>
        </article>
        <p v-if="filteredSteps.length === 0" class="workflow-sidebar-empty">没有匹配的步骤</p>
      </div>
    </section>

    <section class="workflow-sidebar-section">
      <div class="workflow-sidebar-heading">
        <button class="workflow-sidebar-toggle" type="button" @click="conclusionsOpen = !conclusionsOpen">
          <ChevronDown v-if="conclusionsOpen" :size="14" /><ChevronRight v-else :size="14" />排查结论 <small>{{ conclusions.length }}</small>
        </button>
        <button class="workflow-sidebar-add" type="button" title="添加结论" aria-label="添加结论" :disabled="props.readonly" @click="emit('add-conclusion')"><Plus :size="15" /></button>
      </div>
      <div v-if="conclusionsOpen" ref="conclusionList" class="workflow-sidebar-node-list">
        <article v-for="(item, index) in filteredConclusions" :key="item.id" :data-sort-id="item.id" :class="['workflow-sidebar-node', active('conclusion', item.id) && 'active']">
          <button class="workflow-drag-handle" type="button" title="拖动排序" aria-label="拖动结论排序" :disabled="props.readonly || Boolean(query)"><GripVertical :size="14" /></button>
          <button class="workflow-sidebar-node-main" type="button" @click="emit('select', { type: 'conclusion', id: item.id })">
            <span class="workflow-node-kind conclusion"><Flag :size="14" /></span>
            <span><strong>{{ item.name }}</strong><small>{{ item.rootCause || "未填写故障根因" }}</small></span>
            <b v-if="issueCount(item.id)" class="workflow-node-issue"><AlertTriangle :size="10" />{{ issueCount(item.id) }}</b>
          </button>
          <div class="workflow-sidebar-node-actions">
            <button type="button" title="上移" aria-label="上移结论" :disabled="props.readonly || index === 0 || Boolean(query)" @click="emit('move', 'conclusion', item.id, -1)"><ArrowUp :size="12" /></button>
            <button type="button" title="下移" aria-label="下移结论" :disabled="props.readonly || index === filteredConclusions.length - 1 || Boolean(query)" @click="emit('move', 'conclusion', item.id, 1)"><ArrowDown :size="12" /></button>
          </div>
        </article>
        <p v-if="filteredConclusions.length === 0" class="workflow-sidebar-empty">没有匹配的结论</p>
      </div>
    </section>
  </nav>
</template>
