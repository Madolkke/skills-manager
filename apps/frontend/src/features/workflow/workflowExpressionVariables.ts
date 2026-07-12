import type { WorkflowBundle, WorkflowStep } from "../../types";
import { findCollection, workflowSteps } from "./domain/utils";

export type WorkflowExpressionVariableKind = "global" | "step" | "output";

export type WorkflowExpressionVariable = {
  id: string;
  reference: string;
  kind: WorkflowExpressionVariableKind;
  name: string;
  dataType: string;
  source: string;
  aliases: string[];
};

export function workflowExpressionVariables(bundle: WorkflowBundle, sourceStepId: string): WorkflowExpressionVariable[] {
  const variables: WorkflowExpressionVariable[] = [];
  bundle.workflow.inputs.forEach((input) => {
    const key = input.key.trim();
    if (!key) return;
    variables.push({
      id: `global:${input.id}`,
      reference: `global.${key}`,
      kind: "global",
      name: input.name || key,
      dataType: input.dataType,
      source: "全局输入",
      aliases: [key, input.name],
    });
  });

  const steps = workflowSteps(bundle);
  const sourceStep = steps.find((step) => step.id === sourceStepId);
  sourceStep?.inputs.forEach(({ parameter }) => {
    const key = parameter.key.trim();
    if (!key) return;
    variables.push({
      id: `step:${sourceStep.id}:${parameter.id}`,
      reference: `step.${key}`,
      kind: "step",
      name: parameter.name || key,
      dataType: parameter.dataType,
      source: `当前步骤 · ${sourceStep.name || "未命名步骤"}`,
      aliases: [key, parameter.name, sourceStep.name],
    });
  });

  const orderedSteps = sourceStep
    ? [sourceStep, ...steps.filter((step) => step.id !== sourceStep.id)]
    : steps;
  orderedSteps.forEach((step) => appendStepOutputs(variables, bundle, step));
  return variables;
}

export function filterWorkflowExpressionVariables(
  variables: WorkflowExpressionVariable[],
  fragment: string,
): WorkflowExpressionVariable[] {
  const needle = fragment.trim().toLocaleLowerCase();
  if (!needle) return variables;
  return variables.filter((variable) => {
    const terms = [variable.reference, ...variable.reference.split("."), ...variable.aliases, variable.name, variable.source];
    return terms.some((term) => term.trim().toLocaleLowerCase().includes(needle));
  });
}

function appendStepOutputs(
  variables: WorkflowExpressionVariable[],
  bundle: WorkflowBundle,
  step: WorkflowStep,
): void {
  step.collectionCalls.forEach((call) => {
    const definition = findCollection(bundle.collectionSnapshots, call.definition);
    if (!definition) return;
    const callKey = call.key.trim();
    const callName = call.name.trim() || definition.metadata.name.trim() || definition.key.trim() || "未命名采集";
    definition.outputs.forEach((output) => {
      const outputKey = output.key.trim();
      if (!outputKey) return;
      const outputPath = callKey ? `${callKey}.${outputKey}` : outputKey;
      variables.push({
        id: `output:${step.id}:${call.id}:${output.id}`,
        reference: `output.${outputPath}`,
        kind: "output",
        name: output.name || outputKey,
        dataType: output.dataType,
        source: `${step.name || "未命名步骤"} · ${callName}`,
        aliases: [outputPath, callKey, outputKey, output.name, callName, step.name],
      });
    });
  });
}
