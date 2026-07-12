<script setup lang="ts">
import { Panel, VueFlow, useVueFlow, type NodeMouseEvent } from "@vue-flow/core";
import { AlertTriangle, ArrowDownToLine, ArrowRightToLine, Expand, Flag, LoaderCircle, Minus, Play, Plus, Scan, TerminalSquare } from "lucide-vue-next";
import { nextTick, ref, watch } from "vue";
import UiIconButton from "../../../components/ui/UiIconButton.vue";
import type { WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import { useWorkflowGraphLayout } from "../useWorkflowGraphLayout";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";

const props = defineProps<{ bundle: WorkflowBundle; issues: WorkflowValidationIssue[]; selected?: WorkflowSelection; compact?: boolean; direction?: "DOWN" | "RIGHT"; allowFullscreen?: boolean }>();
const emit = defineEmits<{ select: [selection: WorkflowSelection]; "update:direction": [direction: "DOWN" | "RIGHT"]; fullscreen: [] }>();
const { fitView, updateNodeInternals, zoomIn, zoomOut } = useVueFlow();
const flowReady = ref(false);
const { nodes, edges, loading, layouting, reducedMotion, layout, refreshPresentation } = useWorkflowGraphLayout({
  bundle: () => props.bundle,
  issues: () => props.issues,
  selected: () => props.selected,
  compact: () => Boolean(props.compact),
  direction: () => props.direction ?? "DOWN",
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
  await fitView({ padding: props.compact ? 0.15 : 0.22, duration: motionDuration(260), interpolate: "smooth" });
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

function topologyKey(bundle: WorkflowBundle): string {
  return JSON.stringify(bundle.workflow.nodes.map((item) => ({ id: item.id, type: "stepType" in item ? "step" : "conclusion", topology: "topology" in item ? item.topology.map((edge) => [edge.id, edge.target.id]) : [] })));
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
  <div class="workflow-graph">
    <div v-if="loading" class="workflow-graph-state">正在整理流程布局...</div>
    <div v-else-if="nodes.length === 0" class="workflow-graph-state">添加步骤和结论后，流程图会显示在这里。</div>
    <VueFlow v-else :nodes="nodes" :edges="edges" :min-zoom="0.25" :max-zoom="1.5" fit-view-on-init :nodes-draggable="false" :nodes-connectable="false" :zoom-on-double-click="false" @init="handleInit" @node-click="selectNode">
      <Transition name="workflow-state-swap"><div v-if="layouting" class="workflow-graph-layouting"><LoaderCircle :size="13" />正在整理布局</div></Transition>
      <Panel position="top-right" class="workflow-graph-controls">
        <UiIconButton label="放大流程图" size="sm" @click="zoomIn({ duration: motionDuration(180) })"><Plus /></UiIconButton>
        <UiIconButton label="缩小流程图" size="sm" @click="zoomOut({ duration: motionDuration(180) })"><Minus /></UiIconButton>
        <UiIconButton label="适配流程图" size="sm" @click="fitView({ padding: 0.18, duration: motionDuration(260), interpolate: 'smooth' })"><Scan /></UiIconButton>
        <UiIconButton :label="(props.direction ?? 'DOWN') === 'DOWN' ? '切换为从左到右' : '切换为从上到下'" size="sm" @click="emit('update:direction', (props.direction ?? 'DOWN') === 'DOWN' ? 'RIGHT' : 'DOWN')"><Transition name="workflow-icon-swap" mode="out-in"><ArrowRightToLine v-if="(props.direction ?? 'DOWN') === 'DOWN'" key="right" /><ArrowDownToLine v-else key="down" /></Transition></UiIconButton>
        <UiIconButton v-if="props.allowFullscreen" label="全屏查看流程图" size="sm" @click="emit('fullscreen')"><Expand /></UiIconButton>
      </Panel>
      <template #node-workflow="{ data, selected }">
        <div :class="['workflow-graph-node', `is-${data.kind}`, data.entering && 'is-entering', data.leaving && 'is-leaving', (selected || data.isSelected) && 'selected']">
          <div class="workflow-graph-node-head"><span><Flag v-if="data.kind === 'conclusion'" :size="12" /><TerminalSquare v-else :size="12" />{{ data.kind === "conclusion" ? "结论" : "步骤" }}</span><i v-if="data.issueCount"><AlertTriangle :size="11" />{{ data.issueCount }}</i></div>
          <strong>{{ data.title }}</strong><small>{{ data.description || "尚未填写说明" }}</small>
          <div v-if="data.kind === 'step'" class="workflow-graph-node-meta"><span v-if="data.isStart"><Play :size="10" />起点</span><span>{{ data.callCount }} 项采集</span></div>
        </div>
      </template>
    </VueFlow>
  </div>
</template>
