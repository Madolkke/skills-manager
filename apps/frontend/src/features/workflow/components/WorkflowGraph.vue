<script setup lang="ts">
import { MarkerType, Panel, VueFlow, useVueFlow, type Node, type NodeMouseEvent } from "@vue-flow/core";
import ELK from "elkjs/lib/elk.bundled.js";
import { AlertTriangle, ArrowDownToLine, ArrowRightToLine, Expand, Flag, Minus, Play, Plus, Scan, TerminalSquare } from "lucide-vue-next";
import { nextTick, ref, watch } from "vue";
import type { WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../../types";
import { projectWorkflowGraph } from "../domain/graph";
import { workflowConclusions, workflowSteps } from "../domain/utils";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";

const props = defineProps<{ bundle: WorkflowBundle; issues: WorkflowValidationIssue[]; selected?: WorkflowSelection; compact?: boolean; direction?: "DOWN" | "RIGHT"; allowFullscreen?: boolean }>();
const emit = defineEmits<{ select: [selection: WorkflowSelection]; "update:direction": [direction: "DOWN" | "RIGHT"]; fullscreen: [] }>();
interface WorkflowGraphNodeData {
  kind: "step" | "conclusion";
  title: string;
  description: string;
  isStart: boolean;
  callCount: number;
  issueCount: number;
  isSelected: boolean;
}

interface WorkflowGraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
  animated: boolean;
  markerEnd: MarkerType;
  style: { stroke: string; strokeWidth: number };
  labelStyle: { fill: string; fontSize: number };
}

const nodes = ref<Node<WorkflowGraphNodeData>[]>([]);
const edges = ref<WorkflowGraphEdge[]>([]);
const loading = ref(false);
const elk = new ELK();
const { fitView, zoomIn, zoomOut } = useVueFlow();

watch(() => [topologyKey(props.bundle), selectionId(props.selected), issueKey(props.issues), props.direction], () => void layout(), { immediate: true });

async function layout(): Promise<void> {
  loading.value = true;
  const projection = projectWorkflowGraph(props.bundle);
  const direction = props.direction ?? "DOWN";
  const width = props.compact ? 180 : 240;
  const graph = await elk.layout({
    id: "root",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": direction,
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
      "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
      "elk.spacing.nodeNode": props.compact ? "38" : "52",
      "elk.layered.spacing.nodeNodeBetweenLayers": props.compact ? "78" : "96",
    },
    children: projection.nodes.map((item) => ({ id: item.id, width, height: item.type === "conclusion" ? 86 : 104 })),
    edges: projection.edges.map((item) => ({ id: item.id, sources: [item.source], targets: [item.target] })),
  });
  const steps = new Map(workflowSteps(props.bundle).map((item) => [item.id, item]));
  const conclusions = new Map(workflowConclusions(props.bundle).map((item) => [item.id, item]));
  const selectedId = selectionId(props.selected);
  const nextNodes: Node<WorkflowGraphNodeData>[] = [];
  for (const item of graph.children ?? []) {
    const step = steps.get(item.id);
    const conclusion = conclusions.get(item.id);
    const issueCount = props.issues.filter((issue) => "id" in issue.selection && issue.selection.id === item.id).length;
    nextNodes.push({
      id: item.id,
      position: { x: item.x ?? 0, y: item.y ?? 0 },
      type: "workflow",
      data: { kind: step ? "step" : "conclusion", title: step?.name ?? conclusion?.name ?? item.id, description: step?.description ?? conclusion?.rootCause ?? "", isStart: step?.isStart ?? false, callCount: step?.collectionCalls.length ?? 0, issueCount, isSelected: selectedId === item.id },
      draggable: false,
    });
  }
  nodes.value = nextNodes;
  edges.value = projection.edges.map((item) => ({ id: item.id, source: item.source, target: item.target, label: item.label, type: "step", animated: item.loop, markerEnd: MarkerType.ArrowClosed, style: { stroke: item.loop ? "#c84f4c" : "#6d8f5a", strokeWidth: item.loop ? 2 : 1.7 }, labelStyle: { fill: item.loop ? "#a63e3a" : "#46633a", fontSize: 11 } }));
  loading.value = false;
  await nextTick();
  fitView({ padding: props.compact ? 0.15 : 0.22 });
}

function selectionId(selection?: WorkflowSelection): string | undefined {
  return selection && "id" in selection ? selection.id : undefined;
}

function selectNode(event: NodeMouseEvent): void {
  const kind = event.node.data.kind === "conclusion" ? "conclusion" : "step";
  emit("select", { type: kind, id: event.node.id });
}

function topologyKey(bundle: WorkflowBundle): string {
  return JSON.stringify(bundle.workflow.nodes.map((item) => ({ id: item.id, name: item.name, start: "isStart" in item && item.isStart, topology: "topology" in item ? item.topology.map((edge) => [edge.id, edge.target.id, edge.conditionText]) : [] })));
}

function issueKey(issues: WorkflowValidationIssue[]): string {
  return issues.map((item) => `${item.id}:${item.severity}`).join("|");
}
</script>

<template>
  <div class="workflow-graph">
    <div v-if="loading" class="workflow-graph-state">正在整理流程布局...</div>
    <div v-else-if="nodes.length === 0" class="workflow-graph-state">添加步骤和结论后，流程图会显示在这里。</div>
    <VueFlow v-else :nodes="nodes" :edges="edges" :min-zoom="0.25" :max-zoom="1.5" fit-view-on-init :nodes-draggable="false" :nodes-connectable="false" :zoom-on-double-click="false" @node-click="selectNode">
      <Panel position="top-right" class="workflow-graph-controls">
        <button type="button" title="放大" aria-label="放大流程图" @click="zoomIn()"><Plus :size="14" /></button>
        <button type="button" title="缩小" aria-label="缩小流程图" @click="zoomOut()"><Minus :size="14" /></button>
        <button type="button" title="适配视图" aria-label="适配流程图" @click="fitView({ padding: 0.18 })"><Scan :size="14" /></button>
        <button type="button" :title="(props.direction ?? 'DOWN') === 'DOWN' ? '切换为从左到右' : '切换为从上到下'" aria-label="切换流程图方向" @click="emit('update:direction', (props.direction ?? 'DOWN') === 'DOWN' ? 'RIGHT' : 'DOWN')"><ArrowRightToLine v-if="(props.direction ?? 'DOWN') === 'DOWN'" :size="14" /><ArrowDownToLine v-else :size="14" /></button>
        <button v-if="props.allowFullscreen" type="button" title="全屏查看流程图" aria-label="全屏查看流程图" @click="emit('fullscreen')"><Expand :size="14" /></button>
      </Panel>
      <template #node-workflow="{ data, selected }">
        <div :class="['workflow-graph-node', `is-${data.kind}`, (selected || data.isSelected) && 'selected']">
          <div class="workflow-graph-node-head"><span><Flag v-if="data.kind === 'conclusion'" :size="12" /><TerminalSquare v-else :size="12" />{{ data.kind === "conclusion" ? "结论" : "步骤" }}</span><i v-if="data.issueCount"><AlertTriangle :size="11" />{{ data.issueCount }}</i></div>
          <strong>{{ data.title }}</strong><small>{{ data.description || "尚未填写说明" }}</small>
          <div v-if="data.kind === 'step'" class="workflow-graph-node-meta"><span v-if="data.isStart"><Play :size="10" />起点</span><span>{{ data.callCount }} 项采集</span></div>
        </div>
      </template>
    </VueFlow>
  </div>
</template>
