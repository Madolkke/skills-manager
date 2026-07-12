import { MarkerType, Position, type Node } from "@vue-flow/core";
import ELK from "elkjs/lib/elk.bundled.js";
import { onBeforeUnmount, ref, shallowRef } from "vue";
import { useReducedMotion } from "../../composables/useReducedMotion";
import type { WorkflowBundle, WorkflowSelection, WorkflowValidationIssue } from "../../types";
import { projectWorkflowGraph } from "./domain/graph";
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
  label: string;
  type: string;
  animated: boolean;
  markerEnd: MarkerType;
  style: { stroke: string; strokeWidth: number };
  labelStyle: { fill: string; fontSize: number };
}

type GraphLayoutOptions = {
  bundle: () => WorkflowBundle;
  issues: () => WorkflowValidationIssue[];
  selected: () => WorkflowSelection | undefined;
  compact: () => boolean;
  direction: () => "DOWN" | "RIGHT";
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

  /** 计算目标布局，并让已有节点与连线同步移动到新位置。 */
  async function layout(): Promise<boolean> {
    const currentGeneration = ++generation;
    cancelAnimation();
    scheduleLayouting();
    const bundle = options.bundle();
    const projection = projectWorkflowGraph(bundle);
    const compact = options.compact();
    const width = compact ? 180 : 240;
    const graph = await elk.layout({
      id: "root",
      layoutOptions: {
        "elk.algorithm": "layered",
        "elk.direction": options.direction(),
        "elk.edgeRouting": "ORTHOGONAL",
        "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
        "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
        "elk.spacing.nodeNode": compact ? "38" : "52",
        "elk.layered.spacing.nodeNodeBetweenLayers": compact ? "78" : "96",
      },
      children: projection.nodes.map((item) => ({ id: item.id, width, height: item.type === "conclusion" ? 86 : 104 })),
      edges: projection.edges.map((item) => ({ id: item.id, sources: [item.source], targets: [item.target] })),
    });
    if (currentGeneration !== generation) return false;

    const targets = (graph.children ?? []).map<Node<WorkflowGraphNodeData>>((item) => ({
      id: item.id,
      position: { x: item.x ?? 0, y: item.y ?? 0 },
      type: "workflow",
      data: nodeData(item.id),
      draggable: false,
      sourcePosition: options.direction() === "RIGHT" ? Position.Right : Position.Bottom,
      targetPosition: options.direction() === "RIGHT" ? Position.Left : Position.Top,
    }));
    const nextEdges = graphEdges();
    loading.value = false;

    if (reducedMotion.value || nodes.value.length === 0) {
      nodes.value = targets;
      edges.value = nextEdges;
    } else {
      await animateNodes(targets, projection.edges, nextEdges, currentGeneration);
    }
    if (currentGeneration !== generation) return false;
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
    edges.value = graphEdges().filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target));
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

  function graphEdges(): WorkflowGraphEdge[] {
    return projectWorkflowGraph(options.bundle()).edges.map((item) => ({
      id: item.id,
      source: item.source,
      target: item.target,
      label: item.label,
      type: "step",
      animated: item.loop && !reducedMotion.value,
      markerEnd: MarkerType.ArrowClosed,
      style: { stroke: item.loop ? "#c84f4c" : "#6d8f5a", strokeWidth: item.loop ? 2 : 1.7 },
      labelStyle: { fill: item.loop ? "#a63e3a" : "#46633a", fontSize: 11 },
    }));
  }

  function animateNodes(
    targets: Node<WorkflowGraphNodeData>[],
    projectionEdges: Array<{ source: string; target: string }>,
    nextEdges: WorkflowGraphEdge[],
    currentGeneration: number,
  ): Promise<void> {
    const current = new Map(nodes.value.map((node) => [node.id, node]));
    const targetIds = new Set(targets.map((node) => node.id));
    const startPositions = new Map(targets.map((target) => {
      const prior = current.get(target.id);
      if (prior) return [target.id, prior.position] as const;
      const parentId = projectionEdges.find((edge) => edge.target === target.id)?.source;
      return [target.id, current.get(parentId ?? "")?.position ?? target.position] as const;
    }));
    const leaving = nodes.value
      .filter((node) => !targetIds.has(node.id))
      .map<Node<WorkflowGraphNodeData>>((node) => ({ ...node, data: { ...(node.data ?? nodeData(node.id)), leaving: true } }));
    const duration = 260;

    const render = (progress: number) => {
      const eased = 1 - ((1 - progress) ** 3);
      nodes.value = [
        ...targets.map((target) => ({
          ...target,
          position: interpolatePosition(startPositions.get(target.id) ?? target.position, target.position, eased),
          data: { ...(target.data ?? nodeData(target.id)), entering: !current.has(target.id) && progress < 1 },
        })),
        ...(progress < 1 ? leaving : []),
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

export function interpolatePosition(
  start: { x: number; y: number },
  end: { x: number; y: number },
  progress: number,
): { x: number; y: number } {
  return {
    x: start.x + ((end.x - start.x) * progress),
    y: start.y + ((end.y - start.y) * progress),
  };
}
