import { Position, type Node } from "@vue-flow/core";

export type WorkflowGraphDirection = "DOWN" | "RIGHT";

export type WorkflowGraphLabelMetrics = {
  width: number;
  height: number;
};

export type WorkflowGraphEdgeRoute = {
  path: string;
  labelPosition: { x: number; y: number };
  labelSize: WorkflowGraphLabelMetrics;
};

type GraphPoint = { x: number; y: number };
type RoutedSection = { startPoint: GraphPoint; endPoint: GraphPoint; bendPoints?: GraphPoint[] };
type RoutedLabel = { x?: number; y?: number; width?: number; height?: number };
type RoutedEdge = { sections?: RoutedSection[]; labels?: RoutedLabel[] };

const LABEL_HEIGHT = 24;
const WRAPPED_LABEL_HEIGHT = 38;
const BRANCH_COLORS = ["#5b7f45", "#3b73b9", "#a36b15", "#7a5ca7", "#26857e", "#b04f6f"] as const;
const GRAPH_NODE_SIZES = {
  compact: { width: 180, stepHeight: 104, conclusionHeight: 92 },
  expanded: { width: 220, stepHeight: 104, conclusionHeight: 92 },
} as const;

export function workflowGraphNodeSize(compact: boolean, kind: "step" | "conclusion"): { width: number; height: number } {
  const sizes = compact ? GRAPH_NODE_SIZES.compact : GRAPH_NODE_SIZES.expanded;
  return { width: sizes.width, height: kind === "conclusion" ? sizes.conclusionHeight : sizes.stepHeight };
}

export function workflowGraphPorts(direction: WorkflowGraphDirection): Pick<Node, "sourcePosition" | "targetPosition"> {
  return direction === "RIGHT"
    ? { sourcePosition: Position.Right, targetPosition: Position.Left }
    : { sourcePosition: Position.Bottom, targetPosition: Position.Top };
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

export function graphAnimationStart(
  previous: { x: number; y: number } | undefined,
  target: { x: number; y: number },
): { x: number; y: number } {
  return previous ?? target;
}

export function workflowGraphBranchColor(branchIndex: number): string {
  return BRANCH_COLORS[Math.abs(branchIndex) % BRANCH_COLORS.length]!;
}

/** 生成传给 ELK 的标签尺寸，长文本最多占用两行。 */
export function workflowGraphLabelMetrics(label: string, compact: boolean): WorkflowGraphLabelMetrics {
  const maximumWidth = compact ? 156 : 228;
  const naturalWidth = Math.ceil([...label].reduce((width, character) => width + (isWideCharacter(character) ? 11 : 6.5), 18));
  return {
    width: Math.min(maximumWidth, Math.max(52, naturalWidth)),
    height: naturalWidth > maximumWidth ? WRAPPED_LABEL_HEIGHT : LABEL_HEIGHT,
  };
}

/** 将 ELK 返回的正交折线和标签坐标转换为 Vue Flow edge 数据。 */
export function workflowGraphEdgeRoute(edge: RoutedEdge): WorkflowGraphEdgeRoute | null {
  const sections = edge.sections ?? [];
  if (sections.length === 0) return null;
  const path = sections.map((section) => roundedPolyline([
    section.startPoint,
    ...(section.bendPoints ?? []),
    section.endPoint,
  ])).join(" ");
  const label = edge.labels?.[0];
  const fallback = longestSegmentCenter(sections);
  const labelSize = {
    width: label?.width ?? 0,
    height: label?.height ?? 0,
  };
  return {
    path,
    labelPosition: {
      x: label?.x === undefined ? fallback.x : label.x + (labelSize.width / 2),
      y: label?.y === undefined ? fallback.y : label.y + (labelSize.height / 2),
    },
    labelSize,
  };
}

/** 集中维护 ELK 路由间距，保证节点、路径和标签共同参与布局。 */
export function workflowGraphLayoutOptions(compact: boolean, direction: WorkflowGraphDirection): Record<string, string> {
  return {
    "elk.algorithm": "layered",
    "elk.direction": direction,
    "elk.edgeRouting": "ORTHOGONAL",
    "elk.edgeLabels.inline": "true",
    "elk.layered.mergeEdges": "false",
    "elk.layered.mergeHierarchyEdges": "false",
    "elk.layered.unnecessaryBendpoints": "true",
    "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
    "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
    "elk.spacing.nodeNode": compact ? "42" : "56",
    "elk.spacing.edgeEdge": compact ? "14" : "20",
    "elk.spacing.edgeNode": compact ? "22" : "30",
    "elk.spacing.edgeLabel": "10",
    "elk.layered.spacing.edgeEdgeBetweenLayers": compact ? "16" : "22",
    "elk.layered.spacing.edgeNodeBetweenLayers": compact ? "24" : "32",
    "elk.layered.spacing.nodeNodeBetweenLayers": compact ? "94" : "118",
  };
}

function roundedPolyline(points: GraphPoint[]): string {
  if (points.length === 0) return "";
  if (points.length === 1) return `M ${coordinate(points[0]!.x)} ${coordinate(points[0]!.y)}`;
  const commands = [`M ${coordinate(points[0]!.x)} ${coordinate(points[0]!.y)}`];
  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1]!;
    const current = points[index]!;
    const next = points[index + 1]!;
    const radius = Math.min(6, distance(previous, current) / 2, distance(current, next) / 2);
    const before = pointTowards(current, previous, radius);
    const after = pointTowards(current, next, radius);
    commands.push(`L ${coordinate(before.x)} ${coordinate(before.y)} Q ${coordinate(current.x)} ${coordinate(current.y)} ${coordinate(after.x)} ${coordinate(after.y)}`);
  }
  const end = points.at(-1)!;
  commands.push(`L ${coordinate(end.x)} ${coordinate(end.y)}`);
  return commands.join(" ");
}

function longestSegmentCenter(sections: RoutedSection[]): GraphPoint {
  let longest = { start: sections[0]!.startPoint, end: sections[0]!.endPoint, length: -1 };
  sections.forEach((section) => {
    const points = [section.startPoint, ...(section.bendPoints ?? []), section.endPoint];
    for (let index = 1; index < points.length; index += 1) {
      const length = distance(points[index - 1]!, points[index]!);
      if (length > longest.length) longest = { start: points[index - 1]!, end: points[index]!, length };
    }
  });
  return { x: (longest.start.x + longest.end.x) / 2, y: (longest.start.y + longest.end.y) / 2 };
}

function pointTowards(origin: GraphPoint, target: GraphPoint, distanceFromOrigin: number): GraphPoint {
  const total = distance(origin, target);
  if (total === 0) return origin;
  const ratio = distanceFromOrigin / total;
  return { x: origin.x + ((target.x - origin.x) * ratio), y: origin.y + ((target.y - origin.y) * ratio) };
}

function distance(first: GraphPoint, second: GraphPoint): number {
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function coordinate(value: number): number {
  return Math.round(value * 100) / 100;
}

function isWideCharacter(character: string): boolean {
  return character.codePointAt(0)! > 0xff;
}
