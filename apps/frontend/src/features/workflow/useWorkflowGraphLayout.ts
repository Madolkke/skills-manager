import { MarkerType, type EdgeMarkerType, type Node } from "@vue-flow/core";
import ELK from "elkjs/lib/elk.bundled.js";
import { onBeforeUnmount, ref, shallowRef } from "vue";
import { useReducedMotion } from "../../composables/useReducedMotion";
import type { WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../types";
import { projectWorkflowGraph } from "./domain/graph";
import {
  graphAnimationStart,
  interpolatePosition,
  workflowGraphBranchColor,
  workflowGraphEdgeRoute,
  workflowGraphLabelMetrics,
  workflowGraphLayoutOptions,
  workflowGraphNodeSize,
  workflowGraphPorts,
  type WorkflowGraphDirection,
  type WorkflowGraphEdgeRoute,
  type WorkflowGraphLabelMetrics,
} from "./domain/graphRouting";
import { workflowConclusions, workflowSteps } from "./domain/utils";

export interface WorkflowGraphNodeData {
  kind: "step" | "conclusion";
  title: string;
  description: string;
  isStart: boolean;
  callCount: number;
  issueCount: number;
  isSelected: boolean;
  entering?: boolean;
  leaving?: boolean;
}

export interface WorkflowGraphEdge {
  id: string;
  source: string;
  target: string;
  type: "workflow";
  animated: boolean;
  markerEnd: EdgeMarkerType;
  style: { stroke: string; strokeWidth: number };
  data: WorkflowGraphEdgeData;
}

export interface WorkflowGraphEdgeData {
  path: string;
  label: string;
  labelPosition: { x: number; y: number };
  labelSize: WorkflowGraphLabelMetrics;
  loop: boolean;
  color: string;
}

type GraphLayoutOptions = {
  bundle: () => WorkflowBundle;
  issues: () => WorkflowValidationIssue[];
  selected: () => WorkflowSelection | undefined;
  compact: () => boolean;
  direction: () => WorkflowGraphDirection;
};

export function useWorkflowGraphLayout(options: GraphLayoutOptions) {
  const nodes = shallowRef<Node<WorkflowGraphNodeData>[]>([]);
  const edges = shallowRef<WorkflowGraphEdge[]>([]);
  const loading = ref(true);
  const layouting = ref(false);
  const reducedMotion = useReducedMotion();
  const elk = new ELK();
  let generation = 0;
  let frame: number | null = null;
  let finishAnimation: (() => void) | null = null;
  let layoutingTimer: number | null = null;
  let previousDirection: WorkflowGraphDirection | null = null;
  let previousCompact: boolean | null = null;
  let previousStructure = "";
  let routes = new Map<string, WorkflowGraphEdgeRoute>();

  /** 计算目标布局，并让已有节点与连线同步移动到新位置。 */
  async function layout(): Promise<boolean> {
    const currentGeneration = ++generation;
    cancelAnimation();
    scheduleLayouting();
    const bundle = options.bundle();
    const projection = projectWorkflowGraph(bundle);
    const compact = options.compact();
    const direction = options.direction();
    const structure = JSON.stringify({
      nodes: projection.nodes.map((item) => item.id),
      edges: projection.edges.map((item) => [item.id, item.source, item.target]),
    });
    const graph = await elk.layout({
      id: "root",
      layoutOptions: workflowGraphLayoutOptions(compact, direction),
      children: projection.nodes.map((item) => ({ id: item.id, ...workflowGraphNodeSize(compact, item.type) })),
      edges: projection.edges.map((item) => {
        const labelSize = workflowGraphLabelMetrics(item.label, compact);
        return {
          id: item.id,
          sources: [item.source],
          targets: [item.target],
          labels: [{ id: `${item.id}-label`, text: item.label, ...labelSize }],
        };
      }),
    });
    if (currentGeneration !== generation) return false;

    const ports = workflowGraphPorts(direction);
    const targets = (graph.children ?? []).map<Node<WorkflowGraphNodeData>>((item) => ({
      id: item.id,
      position: { x: item.x ?? 0, y: item.y ?? 0 },
      type: "workflow",
      data: nodeData(item.id),
      draggable: false,
      ...ports,
    }));
    const nextRoutes = new Map<string, WorkflowGraphEdgeRoute>();
    (graph.edges ?? []).forEach((edge) => {
      const route = workflowGraphEdgeRoute(edge);
      if (route) nextRoutes.set(edge.id, route);
    });
    routes = nextRoutes;
    const nextEdges = graphEdges(routes);
    loading.value = false;
    const sameNodeIds = nodes.value.length === targets.length
      && nodes.value.every((node) => targets.some((target) => target.id === node.id));
    const shouldFade = nodes.value.length > 0 && (
      previousDirection !== direction
      || previousCompact !== compact
      || (sameNodeIds && previousStructure !== structure)
    );

    if (reducedMotion.value || nodes.value.length === 0) {
      nodes.value = targets;
      edges.value = nextEdges;
    } else if (shouldFade) {
      await fadeInLayout(targets, nextEdges, currentGeneration);
    } else {
      await animateNodes(targets, nextEdges, currentGeneration);
    }
    if (currentGeneration !== generation) return false;
    previousDirection = direction;
    previousCompact = compact;
    previousStructure = structure;
    finishLayouting();
    return true;
  }

  /** 更新名称、选中态、问题数和边标签，不重复调用 ELK。 */
  function refreshPresentation(): void {
    const currentIds = new Set(options.bundle().workflow.nodes.map((node) => node.id));
    nodes.value = nodes.value.map((node) => ({
      ...node,
      data: currentIds.has(node.id)
        ? { ...nodeData(node.id), leaving: node.data?.leaving }
        : { ...(node.data ?? nodeData(node.id)), leaving: true },
    }));
    const nodeIds = new Set(nodes.value.map((node) => node.id));
    edges.value = graphEdges(routes).filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
  }

  function nodeData(id: string): WorkflowGraphNodeData {
    const bundle = options.bundle();
    const step = workflowSteps(bundle).find((item) => item.id === id);
    const conclusion = workflowConclusions(bundle).find((item) => item.id === id);
    const selected = options.selected();
    const issueCount = options.issues().filter((issue) => "id" in issue.selection && issue.selection.id === id).length;
    return {
      kind: step ? "step" : "conclusion",
      title: step?.name ?? conclusion?.name ?? id,
      description: step?.description ?? conclusion?.rootCause ?? "",
      isStart: step?.isStart ?? false,
      callCount: step?.collectionCalls.length ?? 0,
      issueCount,
      isSelected: Boolean(selected && "id" in selected && selected.id === id),
    };
  }

  function graphEdges(edgeRoutes: Map<string, WorkflowGraphEdgeRoute>): WorkflowGraphEdge[] {
    return projectWorkflowGraph(options.bundle()).edges.flatMap((item) => {
      const route = edgeRoutes.get(item.id);
      if (!route) return [];
      const color = workflowGraphBranchColor(item.branchIndex);
      return [{
        id: item.id,
        source: item.source,
        target: item.target,
        type: "workflow",
        animated: item.loop && !reducedMotion.value,
        markerEnd: { type: MarkerType.ArrowClosed, color },
        style: { stroke: color, strokeWidth: item.loop ? 2.1 : 1.8 },
        data: { ...route, label: item.label, loop: item.loop, color },
      }];
    });
  }

  function animateNodes(
    targets: Node<WorkflowGraphNodeData>[],
    nextEdges: WorkflowGraphEdge[],
    currentGeneration: number,
  ): Promise<void> {
    const current = new Map(nodes.value.map((node) => [node.id, node]));
    const startPositions = new Map(targets.map((target) => {
      const prior = current.get(target.id);
      return [target.id, graphAnimationStart(prior?.position, target.position)] as const;
    }));
    const duration = 260;

    const render = (progress: number) => {
      const eased = 1 - ((1 - progress) ** 3);
      nodes.value = [
        ...targets.map((target) => ({
          ...target,
          position: interpolatePosition(startPositions.get(target.id) ?? target.position, target.position, eased),
          data: { ...(target.data ?? nodeData(target.id)), entering: !current.has(target.id) && progress < 1 },
        })),
      ];
    };

    render(0);
    edges.value = nextEdges;

    return new Promise((resolve) => {
      const startedAt = performance.now();
      finishAnimation = resolve;
      const tick = (now: number) => {
        if (currentGeneration !== generation) return cancelAnimation();
        const progress = Math.min(1, (now - startedAt) / duration);
        render(progress);
        if (progress < 1) frame = window.requestAnimationFrame(tick);
        else {
          frame = null;
          finishAnimation = null;
          resolve();
        }
      };
      frame = window.requestAnimationFrame(tick);
    });
  }

  function fadeInLayout(
    targets: Node<WorkflowGraphNodeData>[],
    nextEdges: WorkflowGraphEdge[],
    currentGeneration: number,
  ): Promise<void> {
    const duration = 180;
    nodes.value = targets.map((target) => ({
      ...target,
      data: { ...(target.data ?? nodeData(target.id)), entering: true },
    }));
    edges.value = nextEdges;
    return new Promise((resolve) => {
      const startedAt = performance.now();
      finishAnimation = resolve;
      const tick = (now: number) => {
        if (currentGeneration !== generation) return cancelAnimation();
        if (now - startedAt < duration) {
          frame = window.requestAnimationFrame(tick);
          return;
        }
        frame = null;
        finishAnimation = null;
        nodes.value = targets;
        resolve();
      };
      frame = window.requestAnimationFrame(tick);
    });
  }

  function scheduleLayouting(): void {
    if (layoutingTimer !== null) window.clearTimeout(layoutingTimer);
    layoutingTimer = window.setTimeout(() => {
      layouting.value = true;
      layoutingTimer = null;
    }, 100);
  }

  function finishLayouting(): void {
    if (layoutingTimer !== null) window.clearTimeout(layoutingTimer);
    layoutingTimer = null;
    layouting.value = false;
  }

  function cancelAnimation(): void {
    if (frame !== null) window.cancelAnimationFrame(frame);
    frame = null;
    finishAnimation?.();
    finishAnimation = null;
  }

  onBeforeUnmount(() => {
    generation += 1;
    cancelAnimation();
    finishLayouting();
  });

  return { nodes, edges, loading, layouting, reducedMotion, layout, refreshPresentation };
}
