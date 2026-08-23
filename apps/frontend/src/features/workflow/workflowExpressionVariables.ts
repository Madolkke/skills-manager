import type {
  WorkflowBundle,
  WorkflowConfigCommand,
  WorkflowExpressionEnvironment,
  WorkflowExpressionOutput,
  WorkflowExpressionSchema,
  WorkflowJsonSchema,
  WorkflowStep,
} from "../../types";
import { findCollection } from "./domain/utils";
import { workflowSchemaSummary, workflowSchemaTitle } from "./workflowJsonSchema";
import { isWorkflowExpressionIdentifier } from "./workflowExpressionSyntax";
import { workflowConclusionVisibleSteps, workflowExpressionVisibleSteps } from "./workflowExpressionScope";

export type WorkflowExpressionVariableKind = "global" | "output" | "config" | "device";

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
  indexable?: boolean;
};

export function workflowExpressionVariables(bundle: WorkflowBundle, sourceStepId: string): WorkflowExpressionVariable[] {
  return workflowExpressionVariablesForSteps(bundle, workflowExpressionVisibleSteps(bundle, sourceStepId));
}

export function workflowConclusionExpressionVariables(bundle: WorkflowBundle, conclusionId: string): WorkflowExpressionVariable[] {
  return workflowExpressionVariablesForSteps(bundle, workflowConclusionVisibleSteps(bundle, conclusionId));
}

export function workflowExpressionVariablesForSteps(bundle: WorkflowBundle, steps: WorkflowStep[]): WorkflowExpressionVariable[] {
  const variables: WorkflowExpressionVariable[] = [];
  bundle.workflow.inputs.forEach((input) => {
    const key = input.key.trim();
    if (!isWorkflowExpressionIdentifier(key)) return;
    appendSchemaVariables(variables, {
      id: `input:${input.id}`, reference: `inputs.${key}`, kind: "global",
      name: workflowSchemaTitle(input.schema, key), source: "全局输入", aliases: [key, input.schema.title ?? ""], schema: input.schema,
    });
  });

  bundle.workflow.deviceRoles.forEach((role) => {
    if (!role.schema || role.schema.type !== "object" || !isWorkflowExpressionIdentifier(role.key) || role.key.startsWith("_")) return;
    appendSchemaVariables(variables, {
      id: `device:${role.id}`, reference: `topo.devices.${role.key}`, kind: "device",
      name: role.name || role.key, source: "设备角色", aliases: [role.key, role.name], schema: role.schema,
    });
  });
  const workflowInputKeys = new Set(bundle.workflow.inputs.map((item) => item.key.trim()).filter(Boolean));
  const directOutputCounts = collectDirectOutputCounts(bundle, steps);
  const keyedOutputKeys = collectKeyedOutputKeys(bundle, steps);
  const emittedCallKeys = new Set<string>();
  steps.forEach((step) => appendStepOutputs(variables, bundle, step, workflowInputKeys, directOutputCounts, keyedOutputKeys, emittedCallKeys));
  const config = workflowExpressionEnvironmentForSteps(bundle, steps).config;
  Object.entries(config).forEach(([key, schema]) => appendConfigVariables(variables, key, schema));
  return variables;
}

export function workflowExpressionEnvironment(bundle: WorkflowBundle, sourceStepId?: string): WorkflowExpressionEnvironment {
  return workflowExpressionEnvironmentForSteps(bundle, workflowExpressionVisibleSteps(bundle, sourceStepId));
}

export function workflowConclusionExpressionEnvironment(bundle: WorkflowBundle, conclusionId: string): WorkflowExpressionEnvironment {
  return workflowExpressionEnvironmentForSteps(bundle, workflowConclusionVisibleSteps(bundle, conclusionId));
}

export function workflowExpressionEnvironmentForSteps(bundle: WorkflowBundle, steps: WorkflowStep[]): WorkflowExpressionEnvironment {
  const inputs = Object.fromEntries(bundle.workflow.inputs.filter((item) => item.key.trim()).map((item) => [item.key.trim(), item.schema]));
  const outputs = Object.create(null) as WorkflowExpressionEnvironment["outputs"];
  const directCandidates = new Map<string, WorkflowExpressionOutput | null>();
  steps.forEach((step) => step.collectionCalls.forEach((call) => {
    const callKey = call.key.trim();
    const definition = findCollection(bundle.collectionSnapshots, call.definition);
    if (!definition) return;
    const sampleCount = Math.max(call.sampleCount, 1);
    if (!callKey && sampleCount > 1) return;
    if (callKey) {
      if (Object.hasOwn(outputs, callKey)) return;
      outputs[callKey] = {
        sampleCount,
        fields: Object.fromEntries(definition.outputs.filter((item) => item.key.trim()).map((item) => [item.key.trim(), item.schema])),
      };
      return;
    }
    definition.outputs.forEach((item) => {
      const outputKey = item.key.trim();
      if (!isWorkflowExpressionIdentifier(outputKey) || Object.hasOwn(inputs, outputKey) || directCandidates.has(outputKey)) {
        if (outputKey && directCandidates.has(outputKey)) directCandidates.set(outputKey, null);
        return;
      }
      directCandidates.set(outputKey, { sampleCount, fields: {}, schema: item.schema });
    });
  }));
  directCandidates.forEach((output, key) => {
    if (output && !Object.hasOwn(outputs, key)) outputs[key] = output;
  });

  const deviceProperties: Record<string, WorkflowJsonSchema> = Object.fromEntries(
    bundle.workflow.deviceRoles.filter((role) => role.schema?.type === "object" && isWorkflowExpressionIdentifier(role.key) && !role.key.startsWith("_")).map((role) => [role.key, role.schema!]),
  );
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
  return { inputs, outputs, config, topo: { devices: deviceProperties } };
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
  workflowInputKeys: Set<string>,
  directOutputCounts: Map<string, number>,
  keyedOutputKeys: Set<string>,
  emittedCallKeys: Set<string>,
): void {
  step.collectionCalls.forEach((call) => {
    const definition = findCollection(bundle.collectionSnapshots, call.definition);
    if (!definition) return;
    const callKey = call.key.trim();
    if (!callKey && call.sampleCount > 1) return;
    const callName = call.name.trim() || definition.metadata.name.trim() || definition.key.trim() || "未命名采集";
    if (callKey && !isWorkflowExpressionIdentifier(callKey)) return;
    if (callKey && emittedCallKeys.has(callKey)) return;
    if (callKey) emittedCallKeys.add(callKey);
    if (callKey) {
      const properties = Object.fromEntries(
        definition.outputs
          .filter((candidate) => isWorkflowExpressionIdentifier(candidate.key.trim()))
          .map((candidate) => [candidate.key.trim(), candidate.schema]),
      );
      const objectSchema: WorkflowJsonSchema = { type: "object", title: callName, description: "", properties, required: [], additionalProperties: false };
      const schema: WorkflowJsonSchema = call.sampleCount > 1
        ? { type: "array", title: `${callName} 列表`, description: "", items: objectSchema }
        : objectSchema;
      appendSchemaVariables(variables, {
        id: `output:${step.id}:${call.id}`, reference: `outputs.${callKey}`, kind: "output",
        name: callName, source: `${step.name || "未命名步骤"} · ${callName}`,
        aliases: [callKey, callName, step.name], schema, sampleCount: call.sampleCount > 1 ? call.sampleCount : undefined,
      });
      return;
    }
    definition.outputs.forEach((output) => {
      const outputKey = output.key.trim();
      if (!isWorkflowExpressionIdentifier(outputKey)) return;
      if (!callKey && (workflowInputKeys.has(outputKey) || directOutputCounts.get(outputKey) !== 1 || keyedOutputKeys.has(outputKey))) return;
      const outputPath = callKey ? `${callKey}.${outputKey}` : outputKey;
      appendSchemaVariables(variables, {
        id: `output:${step.id}:${call.id}:${output.id}`, reference: `outputs.${outputPath}`, kind: "output",
        name: workflowSchemaTitle(output.schema, outputKey), source: `${step.name || "未命名步骤"} · ${callName}`,
        aliases: [outputPath, callKey, outputKey, callName, step.name].filter(Boolean), schema: output.schema,
        sampleCount: !callKey && call.sampleCount > 1 ? call.sampleCount : undefined,
      });
    });
  });
}

function collectDirectOutputCounts(bundle: WorkflowBundle, steps: WorkflowStep[]): Map<string, number> {
  const counts = new Map<string, number>();
  steps.forEach((step) => step.collectionCalls.forEach((call) => {
    if (call.key.trim() || call.sampleCount > 1) return;
    const definition = findCollection(bundle.collectionSnapshots, call.definition);
    definition?.outputs.forEach((output) => {
      const key = output.key.trim();
      if (isWorkflowExpressionIdentifier(key)) counts.set(key, (counts.get(key) ?? 0) + 1);
    });
  }));
  return counts;
}

function collectKeyedOutputKeys(bundle: WorkflowBundle, steps: WorkflowStep[]): Set<string> {
  const keys = new Set<string>();
  steps.forEach((step) => step.collectionCalls.forEach((call) => {
    if (!call.key.trim() || !findCollection(bundle.collectionSnapshots, call.definition)) return;
    keys.add(call.key.trim());
  }));
  return keys;
}

function appendSchemaVariables(
  variables: WorkflowExpressionVariable[],
  value: Omit<WorkflowExpressionVariable, "dataType"> & { schema: WorkflowJsonSchema },
): void {
  const { schema, ...base } = value;
  variables.push({ ...base, schema, dataType: workflowSchemaSummary(schema), indexable: schema.type === "array" });
  if (schema.type === "array" && (value.sampleCount ?? 1) > 1) return;
  if (schema.type === "object") {
    Object.entries(schema.properties).forEach(([key, child]) => {
      if (!isWorkflowExpressionIdentifier(key)) return;
      appendSchemaVariables(variables, {
        ...base,
        id: `${base.id}:${key}`,
        reference: `${base.reference}.${key}`,
        name: workflowSchemaTitle(child, key),
        aliases: [...base.aliases, key],
        sampleCount: undefined,
        schema: child,
      });
    });
  } else if (schema.type === "array") {
    appendSchemaVariables(variables, {
      ...base,
      id: `${base.id}:item`,
      reference: `${base.reference}[0]`,
      name: `${base.name} 元素`,
      sampleCount: undefined,
      schema: schema.items,
    });
  }
}

export function expandWorkflowExpressionVariable(
  variable: WorkflowExpressionVariable,
  reference: string,
): WorkflowExpressionVariable[] {
  if (!variable.schema) return [];
  const values: WorkflowExpressionVariable[] = [];
  if (variable.schema.type === "array") {
    appendSchemaVariables(values, {
      ...variable,
      id: `${variable.id}:item`,
      reference,
      sampleCount: undefined,
      schema: variable.schema.items,
    });
    return values;
  }
  appendSchemaVariables(values, {
    ...variable,
    id: `${variable.id}:sample`,
    reference,
    sampleCount: undefined,
    schema: variable.schema,
  });
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
  variables.push({ id: `config:${reference}`, reference, kind: "config", name: schema.title || key, dataType: expressionSchemaSummary(schema), source: "配置匹配", aliases: [key], indexable: schema.type === "array" });
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
