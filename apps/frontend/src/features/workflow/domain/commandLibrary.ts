import type { CollectionDefinition, CollectionOutput, WorkflowParameter } from "../../../types";
import type { CommandLibrarySearchResult } from "../../../types";
import { createWorkflowId } from "./utils";

function schema(value: Record<string, unknown>, fallbackTitle = ""): CollectionOutput["schema"] {
  const type = value.type;
  const base = { title: String(value.title || fallbackTitle), description: String(value.description ?? "") };
  if (type === "object") {
    const additionalProperties = Boolean(value.additionalProperties ?? false);
    return {
      type: "object",
      ...base,
      properties: Object.fromEntries(Object.entries((value.properties ?? {}) as Record<string, Record<string, unknown>>).map(([key, child]) => [key, schema(child, key)])),
      required: Array.isArray(value.required) ? value.required.map(String) : [],
      additionalProperties,
      ...(additionalProperties ? { "x-skillhub-legacy-loose": true } : {}),
    };
  }
  if (type === "array") return { type: "array", ...base, items: schema((value.items ?? { type: "string" }) as Record<string, unknown>, fallbackTitle) };
  if (type === "string" || type === "integer" || type === "number" || type === "boolean") return { type, ...base };
  return { ...base, "x-skillhub-legacy-loose": true };
}

/** 将搜索结果物化为当前 Workflow 的只读来源草稿。 */
export function commandResultToDefinition(result: CommandLibrarySearchResult, index: number): CollectionDefinition {
  const outputSchema = (result.outputSchema ?? {}) as Record<string, unknown>;
  const properties = (outputSchema.properties ?? {}) as Record<string, Record<string, unknown>>;
  const required = new Set(Array.isArray(outputSchema.required) ? outputSchema.required.map(String) : []);
  const outputs: CollectionOutput[] = Object.entries(properties).map(([key, rawSchema]) => ({
    id: `output_${key}`,
    key,
    required: required.has(key),
    schema: schema(rawSchema, key),
  }));
  const captures = result.captureSchema ?? result.captures ?? {};
  const inputs: WorkflowParameter[] = Object.entries(captures).map(([key, value]) => {
    const repeated = typeof value === "object" && value !== null && Boolean((value as Record<string, unknown>).repeated);
    return {
      id: `input_${key}`,
      key,
      required: !(typeof value === "object" && value !== null && Boolean((value as Record<string, unknown>).optional)),
      schema: repeated ? { type: "array", title: `${key} 列表`, description: "", items: { type: "string", title: key, description: "" } } : { type: "string", title: key, description: "" },
    };
  });
  const metadata = (result.metadata ?? {}) as Record<string, unknown>;
  return {
    id: createWorkflowId("collection"),
    revision: 1,
    key: result.key || `system_command_${index}`,
    metadata: {
      name: String(metadata.name ?? result.name ?? result.key),
      description: String(metadata.description ?? result.description ?? ""),
      industry: String(metadata.industry ?? ""),
      device: String(metadata.device ?? ""),
      versions: Array.isArray(metadata.versions) ? metadata.versions.map(String) : [],
      tags: Array.isArray(metadata.tags) ? metadata.tags.map(String) : [],
    },
    spec: {
      collectionType: "cli",
      commandTemplate: result.expression,
      outputSamples: (result.samples ?? []).map((sample, sampleIndex) => ({
        id: sample.id || `sample_${result.id}_${sampleIndex + 1}`,
        name: sample.name || "示例",
        stdout: sample.stdout || "",
        inputValues: {},
      })),
    },
    inputs,
    outputs,
    sourceSystemCommandId: result.source === "system" ? result.id : undefined,
  };
}
