import type { Ref } from "vue";
import type { WorkflowBundle } from "../../types";
import { workflowSteps } from "./domain/utils";
import type { WorkflowEditorSnapshot } from "./useWorkflowEditor";

type Commit = (recipe: (draft: WorkflowEditorSnapshot) => void) => void;

export function createWorkflowOrdering(bundle: Ref<WorkflowBundle | null>, commit: Commit) {
  function reorderWorkflowNodes(kind: "step" | "conclusion", orderedIds: string[]): void {
    commit((draft) => {
      const isTarget = (item: WorkflowBundle["workflow"]["nodes"][number]) => kind === "step" ? "stepType" in item : "nodeType" in item;
      const byId = new Map(draft.bundle.workflow.nodes.filter(isTarget).map((item) => [item.id, item]));
      const ordered = orderedIds.map((id) => byId.get(id)).filter((item) => item !== undefined);
      if (ordered.length !== byId.size) return;
      let index = 0;
      draft.bundle.workflow.nodes = draft.bundle.workflow.nodes.map((item) => isTarget(item) ? ordered[index++]! : item);
    });
  }

  function moveWorkflowNode(kind: "step" | "conclusion", id: string, direction: -1 | 1): void {
    if (!bundle.value) return;
    const items = bundle.value.workflow.nodes.filter((item) => kind === "step" ? "stepType" in item : "nodeType" in item);
    const index = items.findIndex((item) => item.id === id);
    if (index < 0 || index + direction < 0 || index + direction >= items.length) return;
    const ids = items.map((item) => item.id);
    [ids[index], ids[index + direction]] = [ids[index + direction]!, ids[index]!];
    reorderWorkflowNodes(kind, ids);
  }

  function reorderCalls(stepId: string, orderedIds: string[]): void {
    commit((draft) => {
      const step = workflowSteps(draft.bundle).find((item) => item.id === stepId);
      if (!step || orderedIds.length !== step.collectionCalls.length) return;
      const byId = new Map(step.collectionCalls.map((item) => [item.id, item]));
      const ordered = orderedIds.map((id) => byId.get(id)).filter((item) => item !== undefined);
      if (ordered.length === step.collectionCalls.length) step.collectionCalls = ordered;
    });
  }

  return { moveWorkflowNode, reorderWorkflowNodes, reorderCalls };
}
