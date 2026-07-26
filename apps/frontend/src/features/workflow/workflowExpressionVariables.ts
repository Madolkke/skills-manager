import type { WorkflowBundle, WorkflowExpressionEnvironment, WorkflowJsonSchema, WorkflowStep } from "../../types";
import { findCollection, workflowSteps } from "./domain/utils";
import { workflowSchemaSummary, workflowSchemaTitle } from "./workflowJsonSchema";

export type WorkflowExpressionVariableKind = "global" | "output";

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
    if (!pythonIdentifier(key)) return;
    appendSchemaVariables(variables, {
      id: `input:${input.id}`, reference: `inputs.${key}`, kind: "global",
      name: workflowSchemaTitle(input.schema, key), source: "全局输入", aliases: [key, input.schema.title ?? ""], schema: input.schema,
    });
  });

  const steps = workflowSteps(bundle);
  const sourceStep = steps.find((step) => step.id === sourceStepId);

  const orderedSteps = sourceStep
    ? [sourceStep, ...steps.filter((step) => step.id !== sourceStep.id)]
    : steps;
  orderedSteps.forEach((step) => appendStepOutputs(variables, bundle, step));
  return variables;
}

export function workflowExpressionEnvironment(bundle: WorkflowBundle): WorkflowExpressionEnvironment {
  const inputs = Object.fromEntries(bundle.workflow.inputs.filter((item) => item.key.trim()).map((item) => [item.key.trim(), item.schema]));
  const outputs: WorkflowExpressionEnvironment["outputs"] = {};
  workflowSteps(bundle).forEach((step) => step.collectionCalls.forEach((call) => {
    const callKey = call.key.trim();
    const definition = findCollection(bundle.collectionSnapshots, call.definition);
    if (!callKey || !definition) return;
    outputs[callKey] = Object.fromEntries(definition.outputs.filter((item) => item.key.trim()).map((item) => [item.key.trim(), item.schema]));
  }));
  return { inputs, outputs };
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
      if (!pythonIdentifier(callKey) || !pythonIdentifier(outputKey)) return;
      const outputPath = `${callKey}.${outputKey}`;
      appendSchemaVariables(variables, {
        id: `output:${step.id}:${call.id}:${output.id}`, reference: `outputs.${outputPath}`, kind: "output",
        name: workflowSchemaTitle(output.schema, outputKey), source: `${step.name || "未命名步骤"} · ${callName}`,
        aliases: [outputPath, callKey, outputKey, callName, step.name], schema: output.schema,
      });
    });
  });
}

function appendSchemaVariables(
  variables: WorkflowExpressionVariable[],
  value: Omit<WorkflowExpressionVariable, "dataType"> & { schema: WorkflowJsonSchema },
): void {
  const { schema, ...base } = value;
  variables.push({ ...base, dataType: workflowSchemaSummary(schema) });
  if (schema.type === "object") {
    Object.entries(schema.properties).forEach(([key, child]) => {
      if (!pythonIdentifier(key)) return;
      appendSchemaVariables(variables, { ...base, id: `${base.id}:${key}`, reference: `${base.reference}.${key}`, name: workflowSchemaTitle(child, key), aliases: [...base.aliases, key], schema: child });
    });
  } else if (schema.type === "array") {
    appendSchemaVariables(variables, { ...base, id: `${base.id}:item`, reference: `${base.reference}[0]`, name: `${base.name} 元素`, schema: schema.items });
  }
}

function pythonIdentifier(value: string): boolean {
  return /^[A-Za-z_]\w*$/u.test(value) && !new Set(["False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"]).has(value);
}
