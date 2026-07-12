import type { Ref } from "vue";
import type { WorkflowBundle, WorkflowConclusion, WorkflowStep, WorkflowTransition } from "../../types";
import { workflowSteps } from "./domain/utils";
import { newConclusion, newStep, newTransition } from "./editorDefaults";
import type { WorkflowEditorSnapshot } from "./useWorkflowEditor";

type Commit = (recipe: (draft: WorkflowEditorSnapshot) => void, historyGroup?: string) => void;

export type WorkflowPathTargetChoice =
  | { kind: "existing"; id: string }
  | { kind: "step"; name: string; stepType: WorkflowStep["stepType"] }
  | { kind: "conclusion"; name: string };

export type WorkflowPathMutation = { pathId: string; targetId: string };

export function createWorkflowPathEditing(bundle: Ref<WorkflowBundle | null>, commit: Commit) {
  function addPath(stepId: string, choice: WorkflowPathTargetChoice): WorkflowPathMutation | null {
    const prepared = prepareTarget(bundle.value, stepId, choice);
    if (!prepared) return null;
    const path = newTransition({ id: prepared.id });
    commit((draft) => {
      const step = workflowSteps(draft.bundle).find((item) => item.id === stepId);
      if (!step) return;
      insertTarget(draft.bundle, stepId, prepared.node);
      step.topology.push(path);
    });
    return { pathId: path.id, targetId: prepared.id };
  }

  function retargetPath(stepId: string, pathId: string, choice: WorkflowPathTargetChoice): WorkflowPathMutation | null {
    const source = bundle.value && workflowSteps(bundle.value).find((item) => item.id === stepId);
    if (!source?.topology.some((item) => item.id === pathId)) return null;
    const prepared = prepareTarget(bundle.value, stepId, choice);
    if (!prepared) return null;
    commit((draft) => {
      const path = workflowSteps(draft.bundle).find((item) => item.id === stepId)?.topology.find((item) => item.id === pathId);
      if (!path) return;
      insertTarget(draft.bundle, stepId, prepared.node);
      path.target = { id: prepared.id };
    });
    return { pathId, targetId: prepared.id };
  }

  function movePath(stepId: string, id: string, direction: -1 | 1): void {
    commit((draft) => {
      const items = workflowSteps(draft.bundle).find((item) => item.id === stepId)?.topology;
      const index = items?.findIndex((item) => item.id === id) ?? -1;
      if (!items || index < 0 || index + direction < 0 || index + direction >= items.length) return;
      [items[index], items[index + direction]] = [items[index + direction]!, items[index]!];
    });
  }

  function updatePath(stepId: string, id: string, patch: Partial<WorkflowTransition>): void {
    commit(
      (draft) => Object.assign(workflowSteps(draft.bundle).find((item) => item.id === stepId)?.topology.find((item) => item.id === id) ?? {}, patch),
      `path:${stepId}:${id}:${Object.keys(patch).sort().join(",")}`,
    );
  }

  function removePath(stepId: string, id: string): void {
    commit((draft) => {
      const step = workflowSteps(draft.bundle).find((item) => item.id === stepId);
      if (step) step.topology = step.topology.filter((item) => item.id !== id);
    });
  }

  return { addPath, retargetPath, movePath, updatePath, removePath };
}

function prepareTarget(bundle: WorkflowBundle | null, sourceStepId: string, choice: WorkflowPathTargetChoice): { id: string; node?: WorkflowStep | WorkflowConclusion } | null {
  if (!bundle) return null;
  if (choice.kind === "existing") {
    const target = bundle.workflow.nodes.find((item) => item.id === choice.id && item.id !== sourceStepId);
    return target ? { id: target.id } : null;
  }
  const name = choice.name.trim();
  if (!name) return null;
  if (choice.kind === "step") {
    const step = newStep(workflowSteps(bundle).length + 1);
    step.name = name;
    step.stepType = choice.stepType;
    return { id: step.id, node: step };
  }
  const conclusion = newConclusion(bundle.workflow.nodes.filter((item) => "nodeType" in item).length + 1);
  conclusion.name = name;
  return { id: conclusion.id, node: conclusion };
}

function insertTarget(bundle: WorkflowBundle, sourceStepId: string, target?: WorkflowStep | WorkflowConclusion): void {
  if (!target) return;
  if ("stepType" in target) {
    const sourceIndex = bundle.workflow.nodes.findIndex((item) => item.id === sourceStepId);
    bundle.workflow.nodes.splice(sourceIndex + 1, 0, target);
  } else {
    bundle.workflow.nodes.push(target);
  }
}
