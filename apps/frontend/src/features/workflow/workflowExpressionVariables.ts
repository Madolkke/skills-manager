import type { WorkflowBundle, WorkflowConfigCommand, WorkflowExpressionEnvironment, WorkflowExpressionSchema, WorkflowJsonSchema, WorkflowStep } from "../../types";
import { findCollection, workflowSteps } from "./domain/utils";
import { workflowSchemaSummary, workflowSchemaTitle } from "./workflowJsonSchema";
import { isWorkflowExpressionIdentifier } from "./workflowExpressionSyntax";

export type WorkflowExpressionVariableKind = "global" | "output" | "config";

export type WorkflowExpressionVariable = {
  id: string;
  reference: string;
  kind: WorkflowExpressionVariableKind;
  name: string;
  dataType: string;
  source: string;
  aliases: string[];
  schema?: WorkflowJsonSchema;
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

  (sourceStep ? [sourceStep] : steps).forEach((step) => appendStepOutputs(variables, bundle, step));
  const config = workflowExpressionEnvironment(bundle, sourceStepId).config;
  Object.entries(config).forEach(([key, schema]) => appendConfigVariables(variables, key, schema));
  return variables;
}

export function workflowExpressionEnvironment(bundle: WorkflowBundle, sourceStepId?: string): WorkflowExpressionEnvironment {
  const inputs = Object.fromEntries(bundle.workflow.inputs.filter((item) => item.key.trim()).map((item) => [item.key.trim(), item.schema]));
  const outputs: WorkflowExpressionEnvironment["outputs"] = {};
  const steps = sourceStepId ? workflowSteps(bundle).filter((step) => step.id === sourceStepId) : workflowSteps(bundle);
  steps.forEach((step) => step.collectionCalls.forEach((call) => {
    const callKey = call.key.trim();
    const definition = findCollection(bundle.collectionSnapshots, call.definition);
    if (!callKey || !definition || outputs[callKey]) return;
    outputs[callKey] = {
      sampleCount: Math.max(call.sampleCount, 1),
      fields: Object.fromEntries(definition.outputs.filter((item) => item.key.trim()).map((item) => [item.key.trim(), item.schema])),
    };
  }));
  const configCandidates = new Map<string, WorkflowExpressionSchema | null>();
  steps.forEach((step) => step.collectionCalls.forEach((call) => {
    const definition = findCollection(bundle.collectionSnapshots, call.definition);
    if (definition?.spec.collectionType !== "config") return;
    definition.spec.config.commands.forEach((command) => {
      const schema = configCommandSchema(command);
      if (!configCandidates.has(command.name)) configCandidates.set(command.name, schema);
      else configCandidates.set(command.name, null);
    });
  }));
  const config: WorkflowExpressionEnvironment["config"] = Object.fromEntries(
    [...configCandidates.entries()].filter(([, schema]) => schema !== null) as Array<[string, WorkflowExpressionSchema]>,
  );
  return { inputs, outputs, config };
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
        definition.outputs
          .filter((candidate) => isWorkflowExpressionIdentifier(candidate.key.trim()))
          .map((candidate) => [candidate.key.trim(), candidate.schema]),
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
  value: Omit<WorkflowExpressionVariable, "dataType"> & { schema: WorkflowJsonSchema },
): void {
  const { schema, ...base } = value;
  variables.push({ ...base, dataType: workflowSchemaSummary(schema) });
  if (schema.type === "object") {
    Object.entries(schema.properties).forEach(([key, child]) => {
      if (!isWorkflowExpressionIdentifier(key)) return;
      appendSchemaVariables(variables, { ...base, id: `${base.id}:${key}`, reference: `${base.reference}.${key}`, name: workflowSchemaTitle(child, key), aliases: [...base.aliases, key], schema: child });
    });
  } else if (schema.type === "array") {
    appendSchemaVariables(variables, { ...base, id: `${base.id}:item`, reference: `${base.reference}[0]`, name: `${base.name} 元素`, schema: schema.items });
  }
}

export function expandWorkflowExpressionVariable(
  variable: WorkflowExpressionVariable,
  reference: string,
): WorkflowExpressionVariable[] {
  if (!variable.schema) return [];
  const values: WorkflowExpressionVariable[] = [];
  appendSchemaVariables(values, { ...variable, id: `${variable.id}:sample`, reference, sampleCount: undefined, schema: variable.schema });
  return values.slice(1);
}

function configCommandSchema(command: WorkflowConfigCommand): WorkflowExpressionSchema {
  const properties: Record<string, WorkflowExpressionSchema> = {};
  Object.entries(command.captures).forEach(([key, schema]) => { properties[key] = schema; });
  command.children.forEach((child) => { properties[child.name] = configCommandSchema(child); });
  const object: WorkflowExpressionSchema = { type: "object", title: command.name, description: "", properties, required: Object.keys(properties) };
  return command.unique === false ? { type: "array", title: command.name, description: "", items: object } : { type: ["object", "null"], title: command.name, description: "", properties, required: Object.keys(properties) };
}

function appendConfigVariables(variables: WorkflowExpressionVariable[], key: string, schema: WorkflowExpressionSchema, reference = `config.${key}`): void {
  variables.push({ id: `config:${reference}`, reference, kind: "config", name: schema.title || key, dataType: expressionSchemaSummary(schema), source: "配置匹配", aliases: [key] });
  const properties = schema.properties ?? {};
  Object.entries(properties).forEach(([childKey, child]) => {
    if (!isWorkflowExpressionIdentifier(childKey)) return;
    appendConfigVariables(variables, childKey, child, `${reference}.${childKey}`);
  });
  if (schema.type === "array" && schema.items) appendConfigVariables(variables, `${key} 元素`, schema.items, `${reference}[0]`);
}

function expressionSchemaSummary(schema: WorkflowExpressionSchema): string {
  if (Array.isArray(schema.type)) return "object | null";
  if (schema.type === "array") return `array<${schema.items ? expressionSchemaSummary(schema.items) : "any"}>`;
  return schema.type ?? "any";
}
