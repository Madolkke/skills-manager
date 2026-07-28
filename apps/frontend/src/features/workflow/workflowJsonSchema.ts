import type { WorkflowJsonSchema } from "../../types";

export type WorkflowSchemaType = "string" | "integer" | "number" | "boolean" | "object" | "array";

export function newWorkflowSchema(type: WorkflowSchemaType = "string", title = "", description = ""): WorkflowJsonSchema {
  if (type === "object") return { type, title, description, properties: {}, required: [], additionalProperties: false };
  if (type === "array") return { type, title, description, items: newWorkflowSchema("string") };
  return { type, title, description };
}

export function changeWorkflowSchemaType(schema: WorkflowJsonSchema, type: WorkflowSchemaType): WorkflowJsonSchema {
  return newWorkflowSchema(type, schema.title ?? "", schema.description ?? "");
}

export function workflowSchemaTitle(schema: WorkflowJsonSchema, fallback: string): string {
  return schema.title?.trim() || fallback;
}

export function workflowSchemaSummary(schema: WorkflowJsonSchema): string {
  if (!schema.type) return "any（待完善）";
  if (schema.type === "array") return `array<${workflowSchemaSummary(schema.items)}> `;
  if (schema.type === "object") return `object · ${Object.keys(schema.properties).length} 个字段`;
  return schema.type;
}

export function workflowSchemaIsLegacy(schema: WorkflowJsonSchema): boolean {
  if (schema["x-skillhub-legacy-loose"]) return true;
  if (schema.type === "object") return Object.values(schema.properties).some(workflowSchemaIsLegacy);
  if (schema.type === "array") return workflowSchemaIsLegacy(schema.items);
  return false;
}

export function canonicalWorkflowSchema(schema: WorkflowJsonSchema): WorkflowJsonSchema {
  if (schema.type === "object") {
    const properties = Object.fromEntries(Object.entries(schema.properties).sort(([left], [right]) => left.localeCompare(right)).map(([key, child]) => [key, canonicalWorkflowSchema(child)]));
    return { ...schema, properties, required: [...new Set(schema.required)].filter((key) => key in properties).sort() };
  }
  if (schema.type === "array") return { ...schema, items: canonicalWorkflowSchema(schema.items) };
  return { ...schema };
}

export function validWorkflowSchema(schema: WorkflowJsonSchema): boolean {
  if (!schema.type) return schema["x-skillhub-legacy-loose"] === true;
  if (schema.type === "array") return validWorkflowSchema(schema.items);
  if (schema.type !== "object") return true;
  const keys = Object.keys(schema.properties);
  return schema.additionalProperties === false
    && keys.every((key) => Boolean(key.trim()) && validWorkflowSchema(schema.properties[key]))
    && new Set(schema.required).size === schema.required.length
    && schema.required.every((key) => key in schema.properties);
}

export function workflowSchemasAssignable(source: WorkflowJsonSchema, target: WorkflowJsonSchema): boolean {
  if (!source.type || !target.type) return true;
  if (source.type !== target.type && !(source.type === "integer" && target.type === "number")) return false;
  if (source.type === "array" && target.type === "array") return workflowSchemasAssignable(source.items, target.items);
  if (source.type !== "object" || target.type !== "object") return true;
  return target.required.every((key) => Boolean(source.properties[key] && target.properties[key] && workflowSchemasAssignable(source.properties[key], target.properties[key])))
    && Object.entries(target.properties).every(([key, child]) => !source.properties[key] || workflowSchemasAssignable(source.properties[key], child));
}

export function workflowValueMatchesSchema(value: unknown, schema: WorkflowJsonSchema): boolean {
  if (!schema.type) return true;
  if (schema.type === "string") return typeof value === "string";
  if (schema.type === "boolean") return typeof value === "boolean";
  if (schema.type === "integer") return typeof value === "number" && Number.isInteger(value);
  if (schema.type === "number") return typeof value === "number" && Number.isFinite(value);
  if (schema.type === "array") return Array.isArray(value) && value.every((item) => workflowValueMatchesSchema(item, schema.items));
  if (schema.type !== "object") return false;
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  if (schema.required.some((key) => !(key in record))) return false;
  if (!schema.additionalProperties && Object.keys(record).some((key) => !(key in schema.properties))) return false;
  return Object.entries(schema.properties).every(([key, child]) => !(key in record) || workflowValueMatchesSchema(record[key], child));
}

export function parseScalarLiteral(value: string, schema: WorkflowJsonSchema): unknown {
  if (schema.type === "boolean") return value === "true";
  if (schema.type === "integer") return Number.parseInt(value, 10);
  if (schema.type === "number") return Number(value);
  return value;
}
