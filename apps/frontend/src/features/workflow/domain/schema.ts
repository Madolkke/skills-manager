import { z } from "zod";
import type { CollectionDefinition, WorkflowBundle } from "../../../types";

const ref = z.object({ id: z.string(), revision: z.number() }).strict();
const parameter = z.object({ id: z.string(), key: z.string(), name: z.string(), description: z.string(), dataType: z.string(), required: z.boolean() }).strict();
const binding = z.object({ kind: z.enum(["workflow_input", "collection_output", "literal"]), reference: z.record(z.string(), z.string()), value: z.unknown().optional() }).strict();
const metadata = z.object({ name: z.string(), code: z.string(), description: z.string(), symptom: z.string().default(""), industry: z.string(), device: z.string(), versions: z.array(z.string()) }).strict();
const role = z.object({ id: z.string(), key: z.string(), name: z.string(), description: z.string(), required: z.boolean() }).strict();
const collectionMetadata = z.object({ name: z.string(), description: z.string(), industry: z.string(), device: z.string(), versions: z.array(z.string()), tags: z.array(z.string()) }).strict();
const output = z.object({ id: z.string(), key: z.string(), description: z.string(), dataType: z.string() }).strict();
const sample = z.object({ id: z.string(), name: z.string(), stdout: z.string(), inputValues: z.record(z.string(), z.unknown()) }).strict();

export const collectionDefinitionSchema: z.ZodType<CollectionDefinition> = z.object({
  id: z.string(),
  revision: z.number(),
  key: z.string(),
  metadata: collectionMetadata,
  spec: z.object({ collectionType: z.literal("cli"), commandTemplate: z.string(), outputSamples: z.array(sample) }).strict(),
  inputs: z.array(parameter),
  outputs: z.array(output),
  forkedFrom: ref.optional(),
}).strict();

const call = z.object({
  id: z.string(), key: z.string(), name: z.string(), definition: ref, deviceRoleId: z.string().optional(), sampleCount: z.number(), inputBindings: z.record(z.string(), binding),
}).strict();
const target = z.object({ id: z.string() }).strict();
const transition = z.object({ id: z.string(), target, conditionText: z.string(), conditionExpression: z.string() }).strict();
const baseStep = { id: z.string(), name: z.string(), description: z.string(), isStart: z.boolean(), collectionCalls: z.array(call), topology: z.array(transition) };
const expressionStep = z.object({ ...baseStep, stepType: z.literal("expression") }).strict();
const scriptStep = z.object({ ...baseStep, stepType: z.literal("script"), script: z.object({ language: z.string(), source: z.string(), options: z.record(z.string(), z.unknown()) }).strict().optional() }).strict();
const conclusion = z.object({ id: z.string(), name: z.string(), rootCause: z.string(), repairRecommendation: z.string(), nodeType: z.literal("conclusion") }).strict();

export const workflowBundleSchema: z.ZodType<WorkflowBundle> = z.object({
  documentType: z.literal("workflow_bundle"),
  workflow: z.object({ id: z.string(), revision: z.number(), metadata, inputs: z.array(parameter), deviceRoles: z.array(role), nodes: z.array(z.union([expressionStep, scriptStep, conclusion])) }).strict(),
  collectionSnapshots: z.array(collectionDefinitionSchema),
}).strict();

export function parseWorkflowBundle(value: unknown): WorkflowBundle {
  return workflowBundleSchema.parse(value);
}
