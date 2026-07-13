<script setup lang="ts">
import { Handle, Panel, Position, VueFlow, useVueFlow, type NodeMouseEvent } from "@vue-flow/core";
import { AlertTriangle, ArrowDownToLine, ArrowRightToLine, Flag, LoaderCircle, Maximize2, Minimize2, Minus, Play, Plus, Scan, TerminalSquare } from "lucide-vue-next";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import { useWorkflowGraphLayout } from "../useWorkflowGraphLayout";
import WorkflowGraphEdge from "./WorkflowGraphEdge.vue";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";

const props = defineProps<{ bundle: WorkflowBundle; issues: WorkflowValidationIssue[]; selected?: WorkflowSelection; compact?: boolean; direction?: "DOWN" | "RIGHT"; allowExpand?: boolean; expanded?: boolean }>();
const emit = defineEmits<{ select: [selection: WorkflowSelection]; "update:direction": [direction: "DOWN" | "RIGHT"]; "toggle-expand": [] }>();
const { fitView, updateNodeInternals, zoomIn, zoomOut } = useVueFlow();
const flowReady = ref(false);
const graphRoot = ref<HTMLElement | null>(null);
let viewportObserver: ResizeObserver | null = null;
let viewportTimer: number | null = null;
const { nodes, edges, loading, layouting, reducedMotion, layout, refreshPresentation } = useWorkflowGraphLayout({
  bundle: () => props.bundle,
  issues: () => props.issues,
  selected: () => props.selected,
  compact: () => Boolean(props.compact),
  direction: () => props.direction ?? "RIGHT",
});

onMounted(() => {
  if (!graphRoot.value || typeof ResizeObserver === "undefined") return;
  viewportObserver = new ResizeObserver(scheduleViewportFit);
  viewportObserver.observe(graphRoot.value);
});
onBeforeUnmount(() => {
  viewportObserver?.disconnect();
  if (viewportTimer !== null) window.clearTimeout(viewportTimer);
});

watch(() => [topologyKey(props.bundle), props.direction, props.compact], () => void relayout(), { immediate: true });
watch(() => [presentationKey(props.bundle), selectionId(props.selected), issueKey(props.issues), reducedMotion.value], refreshPresentation);
watch(() => nodes.value.length, (count) => {
  if (count === 0) flowReady.value = false;
});

async function relayout(): Promise<void> {
  if (!await layout()) return;
  await nextTick();
  if (!flowReady.value) return;
  updateNodeInternals();
  await nextTick();
  await fitView({ padding: props.compact ? 0.1 : 0.14, duration: motionDuration(260), interpolate: "smooth" });
}

function selectionId(selection?: WorkflowSelection): string | undefined {
  return selection && "id" in selection ? selection.id : undefined;
}

function selectNode(event: NodeMouseEvent): void {
  const kind = event.node.data.kind === "conclusion" ? "conclusion" : "step";
  emit("select", { type: kind, id: event.node.id });
}

function handleInit(): void {
  flowReady.value = true;
}

function scheduleViewportFit(): void {
  if (viewportTimer !== null) window.clearTimeout(viewportTimer);
  viewportTimer = window.setTimeout(() => {
    viewportTimer = null;
    if (!flowReady.value || nodes.value.length === 0 || layouting.value) return;
    void fitView({ padding: props.compact ? 0.1 : 0.14, duration: motionDuration(180), interpolate: "smooth" });
  }, 120);
}

function topologyKey(bundle: WorkflowBundle): string {
  return JSON.stringify(bundle.workflow.nodes.map((item) => ({ id: item.id, type: "stepType" in item ? "step" : "conclusion", topology: "topology" in item ? item.topology.map((edge) => [edge.id, edge.target.id, edge.conditionText]) : [] })));
}

function presentationKey(bundle: WorkflowBundle): string {
  return JSON.stringify(bundle.workflow.nodes.map((item) => ({ id: item.id, name: item.name, description: "description" in item ? item.description : item.rootCause, start: "isStart" in item && item.isStart, calls: "collectionCalls" in item ? item.collectionCalls.length : 0, labels: "topology" in item ? item.topology.map((edge) => [edge.id, edge.conditionText]) : [] })));
}

function issueKey(issues: WorkflowValidationIssue[]): string {
  return issues.map((item) => `${item.id}:${item.severity}`).join("|");
}

function motionDuration(duration: number): number {
  return reducedMotion.value ? 0 : duration;
}
</script>

<template>
  <div ref="graphRoot" :class="['workflow-graph', props.compact && 'is-compact', props.expanded && 'is-expanded']">
    <div v-if="loading" class="workflow-graph-state">正在整理流程布局...</div>
    <div v-else-if="nodes.length === 0" class="workflow-graph-state">添加步骤和结论后，流程图会显示在这里。</div>
    <VueFlow v-else :nodes="nodes" :edges="edges" :min-zoom="0.25" :max-zoom="1.5" fit-view-on-init :nodes-draggable="false" :nodes-connectable="false" :zoom-on-double-click="false" @init="handleInit" @node-click="selectNode">
      <Transition name="workflow-state-swap"><div v-if="layouting" class="workflow-graph-layouting"><LoaderCircle :size="13" />正在整理布局</div></Transition>
      <Panel position="top-right" class="workflow-graph-controls">
        <UiIconButton label="放大流程图" size="sm" @click="zoomIn({ duration: motionDuration(180) })"><Plus /></UiIconButton>
        <UiIconButton label="缩小流程图" size="sm" @click="zoomOut({ duration: motionDuration(180) })"><Minus /></UiIconButton>
        <UiIconButton label="适配流程图" size="sm" @click="fitView({ padding: 0.12, duration: motionDuration(260), interpolate: 'smooth' })"><Scan /></UiIconButton>
        <UiIconButton :label="(props.direction ?? 'RIGHT') === 'DOWN' ? '切换为从左到右' : '切换为从上到下'" size="sm" @click="emit('update:direction', (props.direction ?? 'RIGHT') === 'DOWN' ? 'RIGHT' : 'DOWN')"><Transition name="workflow-icon-swap" mode="out-in"><ArrowRightToLine v-if="(props.direction ?? 'RIGHT') === 'DOWN'" key="right" /><ArrowDownToLine v-else key="down" /></Transition></UiIconButton>
        <UiIconButton v-if="props.allowExpand" :label="props.expanded ? '收回流程图' : '展开流程图'" :pressed="props.expanded" size="sm" @click="emit('toggle-expand')"><Minimize2 v-if="props.expanded" /><Maximize2 v-else /></UiIconButton>
      </Panel>
      <template #edge-workflow="edgeProps"><WorkflowGraphEdge v-bind="edgeProps" /></template>
      <template #node-workflow="{ data, selected }">
        <div :class="['workflow-graph-node', `is-${data.kind}`, data.entering && 'is-entering', data.leaving && 'is-leaving', (selected || data.isSelected) && 'selected']">
          <Handle class="workflow-graph-handle" type="target" :connectable="false" :position="(props.direction ?? 'RIGHT') === 'RIGHT' ? Position.Left : Position.Top" />
          <div class="workflow-graph-node-head"><span><Flag v-if="data.kind === 'conclusion'" :size="12" /><TerminalSquare v-else :size="12" />{{ data.kind === "conclusion" ? "结论" : "步骤" }}</span><i v-if="data.issueCount"><AlertTriangle :size="11" />{{ data.issueCount }}</i></div>
          <strong>{{ data.title }}</strong><small>{{ data.description || "尚未填写说明" }}</small>
          <div v-if="data.kind === 'step'" class="workflow-graph-node-meta"><span v-if="data.isStart"><Play :size="10" />起点</span><span>{{ data.callCount }} 项采集</span></div>
          <Handle class="workflow-graph-handle" type="source" :connectable="false" :position="(props.direction ?? 'RIGHT') === 'RIGHT' ? Position.Right : Position.Bottom" />
        </div>
      </template>
    </VueFlow>
  </div>
</template>
