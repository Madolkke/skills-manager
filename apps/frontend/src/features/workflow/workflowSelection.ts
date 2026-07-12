import type { CollectionDefinition, WorkflowBundle, WorkflowSelection } from "../../types";
import { workflowConclusions, workflowSteps } from "./domain/utils";

export function validWorkflowSelection(
  previous: WorkflowSelection,
  bundle: WorkflowBundle | null,
  catalog: CollectionDefinition[],
): WorkflowSelection {
  if (!bundle) return { type: "metadata" };
  if (previous.type === "step") {
    const step = workflowSteps(bundle).find((item) => item.id === previous.id);
    if (!step) return { type: "metadata" };
    if (previous.itemId && !step.collectionCalls.some((item) => item.id === previous.itemId)) {
      return { type: "step", id: previous.id, section: previous.section };
    }
    return previous;
  }
  if (previous.type === "conclusion") {
    return workflowConclusions(bundle).some((item) => item.id === previous.id) ? previous : { type: "metadata" };
  }
  if (previous.type === "collection") {
    const revisions = catalog.filter((item) => item.id === previous.id).map((item) => item.revision);
    const revision = revisions.length ? Math.max(...revisions) : undefined;
    return revision ? { ...previous, revision } : { type: "collections" };
  }
  return previous;
}
