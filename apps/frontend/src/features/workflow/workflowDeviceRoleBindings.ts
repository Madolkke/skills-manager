import type { DeviceRole, WorkflowJsonSchema } from "../../types";
import { isWorkflowDeviceIdentifier, isWorkflowDeviceSchemaProjectable, workflowDeviceRoleExpressionPath } from "./workflowDeviceRoleSchema";

export type WorkflowDeviceFieldCandidate = {
  roleId: string;
  roleKey: string;
  roleName: string;
  path: string;
  reference: string;
  schema: WorkflowJsonSchema;
};

export type WorkflowDeviceFieldResolution = {
  status: "ok" | "role_missing" | "path_invalid";
  candidate?: WorkflowDeviceFieldCandidate;
};

export function workflowDeviceFieldCandidates(
  roles: DeviceRole[],
  preferredRoleId?: string,
): WorkflowDeviceFieldCandidate[] {
  return [...roles]
    .sort((left, right) => Number(right.id === preferredRoleId) - Number(left.id === preferredRoleId))
    .flatMap(roleCandidates);
}

export function resolveWorkflowDeviceField(
  roles: DeviceRole[],
  roleId: string,
  path: string,
): WorkflowDeviceFieldResolution {
  const role = roles.find((item) => item.id === roleId);
  if (!role) return { status: "role_missing" };
  if (!path || path.split(".").some((part) => !isWorkflowDeviceIdentifier(part))) return { status: "path_invalid" };
  const candidate = roleCandidates(role).find((item) => item.path === path);
  return candidate ? { status: "ok", candidate } : { status: "path_invalid" };
}

function roleCandidates(role: DeviceRole): WorkflowDeviceFieldCandidate[] {
  if (!isWorkflowDeviceIdentifier(role.key) || !isWorkflowDeviceSchemaProjectable(role.schema)) return [];
  return collectObjectFields(role, role.schema, "");
}

function collectObjectFields(role: DeviceRole, schema: WorkflowJsonSchema, parentPath: string): WorkflowDeviceFieldCandidate[] {
  if (schema.type !== "object") return [];
  return Object.entries(schema.properties).flatMap(([key, child]) => {
    if (!isWorkflowDeviceIdentifier(key) || child.type === "array") return [];
    const path = parentPath ? `${parentPath}.${key}` : key;
    const item: WorkflowDeviceFieldCandidate = {
      roleId: role.id,
      roleKey: role.key,
      roleName: role.name,
      path,
      reference: `${workflowDeviceRoleExpressionPath(role)}.${path}`,
      schema: child,
    };
    return child.type === "object" ? [item, ...collectObjectFields(role, child, path)] : [item];
  });
}
