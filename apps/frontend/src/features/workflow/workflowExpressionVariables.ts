import type { WorkflowBundle, WorkflowExpressionEnvironment, WorkflowJsonSchema, WorkflowStep } from "../../types";
import { findCollection, workflowSteps } from "./domain/utils";
import { workflowSchemaSummary, workflowSchemaTitle } from "./workflowJsonSchema";
import { isWorkflowExpressionIdentifier } from "./workflowExpressionSyntax";

export type WorkflowExpressionVariableKind = "global" | "output";

export type WorkflowExpressionVariable = {
  id: string;
  reference: string;
  kind: WorkflowExpressionVariableKind;
  name: string;
  dataType: string;
  source: string;
  aliases: string[];
  schema: WorkflowJsonSchema;
  sampleCount?: number;
};

export function workflowExpressionVariables(bundle: WorkflowBundle, sourceStepId: string): WorkflowExpressionVariable[] {
  const variables: WorkflowExpressionVariable[] = [];
  bundle.workflow.inputs.forEach((input) => {
    const key = input.key.trim();
    if (!isWorkflowExpressionIdentifier(key)) return;
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
    if (!callKey || !definition || outputs[callKey]) return;
    outputs[callKey] = {
      sampleCount: Math.max(call.sampleCount, 1),
      fields: Object.fromEntries(definition.outputs.filter((item) => item.key.trim()).map((item) => [item.key.trim(), item.schema])),
    };
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
    if (!isWorkflowExpressionIdentifier(callKey)) return;
    if (call.sampleCount > 1) {
      const properties = Object.fromEntries(
        definition.outputs.filter((output) => isWorkflowExpressionIdentifier(output.key.trim())).map((output) => [output.key.trim(), output.schema]),
      );
      variables.push({
        id: `output:${step.id}:${call.id}`,
        reference: `outputs.${callKey}`,
        kind: "output",
        name: callName,
        dataType: `${call.sampleCount} 个采集结果`,
        source: `${step.name || "未命名步骤"} · ${callName}`,
        aliases: [callKey, callName, step.name],
        schema: { type: "object", title: callName, description: "", properties, required: [], additionalProperties: false },
        sampleCount: call.sampleCount,
      });
      return;
    }
    definition.outputs.forEach((output) => {
      const outputKey = output.key.trim();
      if (!isWorkflowExpressionIdentifier(outputKey)) return;
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
  value: Omit<WorkflowExpressionVariable, "dataType">,
): void {
  const { schema } = value;
  variables.push({ ...value, dataType: workflowSchemaSummary(schema) });
  if (schema.type === "object") {
    Object.entries(schema.properties).forEach(([key, child]) => {
      if (!isWorkflowExpressionIdentifier(key)) return;
      appendSchemaVariables(variables, { ...value, id: `${value.id}:${key}`, reference: `${value.reference}.${key}`, name: workflowSchemaTitle(child, key), aliases: [...value.aliases, key], schema: child });
    });
  } else if (schema.type === "array") {
    appendSchemaVariables(variables, { ...value, id: `${value.id}:item`, reference: `${value.reference}[0]`, name: `${value.name} 元素`, schema: schema.items });
  }
}

export function expandWorkflowExpressionVariable(
  variable: WorkflowExpressionVariable,
  reference: string,
): WorkflowExpressionVariable[] {
  const values: WorkflowExpressionVariable[] = [];
  appendSchemaVariables(values, { ...variable, id: `${variable.id}:sample`, reference, sampleCount: undefined });
  return values.slice(1);
}
