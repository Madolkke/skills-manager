import { z } from "zod";
import type { CollectionDefinition, WorkflowBundle, WorkflowConfigCapture, WorkflowJsonSchema } from "../../../types";

const ref = z.object({ id: z.string(), revision: z.number() }).strict();
const schemaMetadata = { title: z.string(), description: z.string(), "x-skillhub-legacy-loose": z.boolean().optional() };
const jsonSchema: z.ZodType<WorkflowJsonSchema> = z.lazy(() => z.union([
  z.object({ ...schemaMetadata, type: z.enum(["string", "integer", "number", "boolean"]) }).strict(),
  z.object({ ...schemaMetadata, type: z.literal("object"), properties: z.record(z.string(), jsonSchema), required: z.array(z.string()), additionalProperties: z.boolean() }).strict(),
  z.object({ ...schemaMetadata, type: z.literal("array"), items: jsonSchema }).strict(),
  z.object({ type: z.undefined().optional(), title: z.string().optional(), description: z.string().optional(), "x-skillhub-legacy-loose": z.literal(true) }).strict(),
]));
const parameter = z.object({ id: z.string(), key: z.string(), required: z.boolean(), schema: jsonSchema }).strict();
const binding = z.object({ kind: z.enum(["workflow_input", "collection_output", "literal"]), reference: z.record(z.string(), z.string()), value: z.unknown().optional() }).strict();
const metadata = z.object({ name: z.string(), code: z.string(), description: z.string(), symptom: z.string().default(""), industry: z.string(), device: z.string(), versions: z.array(z.string()) }).strict();
const role = z.object({ id: z.string(), key: z.string(), name: z.string(), description: z.string(), required: z.boolean() }).strict();
const collectionMetadata = z.object({ name: z.string(), description: z.string(), industry: z.string(), device: z.string(), versions: z.array(z.string()), tags: z.array(z.string()) }).strict();
const output = z.object({ id: z.string(), key: z.string(), required: z.boolean(), schema: jsonSchema }).strict();
const sample = z.object({ id: z.string(), name: z.string(), stdout: z.string(), inputValues: z.record(z.string(), z.unknown()) }).strict();
const logQuery = z.object({ id: z.string(), name: z.string(), sql: z.string(), outputIds: z.array(z.string()) }).strict();
const logSample = z.object({ id: z.string(), name: z.string(), text: z.string() }).strict();
const configCapture = z.object({ ...schemaMetadata, type: z.enum(["string", "integer", "number", "boolean"]) }).strict();
type ConfigCommandValue = { name: string; unique: boolean; pattern: string; captures: Record<string, WorkflowConfigCapture>; children: ConfigCommandValue[] };
const configCommand: z.ZodType<ConfigCommandValue> = z.lazy(() => z.object({
  name: z.string(), unique: z.boolean(), pattern: z.string(), captures: z.record(z.string(), configCapture), children: z.array(configCommand),
}).strict());
const collectionSpec = z.discriminatedUnion("collectionType", [
  z.object({ collectionType: z.literal("cli"), commandTemplate: z.string(), outputSamples: z.array(sample), commandParameterSyntax: z.literal("angle-v1").optional() }).strict(),
  z.object({ collectionType: z.literal("log"), sqlDialect: z.literal("duckdb"), queries: z.array(logQuery), outputSamples: z.array(logSample) }).strict(),
  z.object({ collectionType: z.literal("config"), config: z.object({ commands: z.array(configCommand) }).strict() }).strict(),
]);

export const collectionDefinitionSchema: z.ZodType<CollectionDefinition> = z.object({
  id: z.string(),
  revision: z.number(),
  key: z.string(),
  metadata: collectionMetadata,
  spec: collectionSpec,
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
const conclusion = z.object({ id: z.string(), name: z.string(), severity: z.enum(["info", "warning", "error", "critical"]).default("info"), rootCause: z.string(), repairRecommendation: z.string(), nodeType: z.literal("conclusion") }).strict();

export const workflowBundleSchema: z.ZodType<WorkflowBundle> = z.object({
  documentType: z.literal("workflow_bundle"),
  workflow: z.object({ id: z.string(), revision: z.number(), metadata, inputs: z.array(parameter), deviceRoles: z.array(role), nodes: z.array(z.union([expressionStep, scriptStep, conclusion])) }).strict(),
  collectionSnapshots: z.array(collectionDefinitionSchema),
}).strict();

export function parseWorkflowBundle(value: unknown): WorkflowBundle {
  return workflowBundleSchema.parse(value);
}
