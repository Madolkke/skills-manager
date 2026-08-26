import type { DeviceRole, WorkflowJsonSchema } from "../../types";
import { isWorkflowExpressionIdentifier } from "./workflowExpressionSyntax";

const scalarTypes = new Set(["string", "integer", "number", "boolean"]);

export function isWorkflowDeviceIdentifier(value: string): boolean {
  const key = value.trim();
  return isWorkflowExpressionIdentifier(key) && !key.startsWith("_");
}

export function isWorkflowDeviceSchemaProjectable(schema: WorkflowJsonSchema | undefined): schema is WorkflowJsonSchema & { type: "object" } {
  if (!schema || schema.type !== "object") return false;
  return isWorkflowDeviceSchemaNodeProjectable(schema);
}

export function workflowDeviceRoleExpressionPath(role: Pick<DeviceRole, "key">): string {
  return `topo.devices.${role.key.trim() || "<roleKey>"}`;
}

export function workflowDeviceRoleSchemaFieldCount(role: Pick<DeviceRole, "schema">): number {
  return role.schema?.type === "object" ? Object.keys(role.schema.properties).length : 0;
}

function isWorkflowDeviceSchemaNodeProjectable(schema: WorkflowJsonSchema): boolean {
  if (scalarTypes.has(schema.type ?? "")) return true;
  if (schema.type === "array") return isWorkflowDeviceSchemaNodeProjectable(schema.items);
  if (schema.type !== "object") return false;
  if (schema.additionalProperties !== false) return false;
  const keys = Object.keys(schema.properties);
  return new Set(schema.required).size === schema.required.length
    && schema.required.every((key) => key in schema.properties)
    && keys.every((key) => isWorkflowDeviceIdentifier(key) && isWorkflowDeviceSchemaNodeProjectable(schema.properties[key]!));
}
