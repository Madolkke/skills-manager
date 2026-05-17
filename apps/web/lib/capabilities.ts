import type { SkillCapabilities, SkillPermission } from "@/lib/types";

const permissionDeniedReasons: Record<SkillPermission, string> = {
  "role.manage": "需要 owner 权限。",
  "variant.promote": "需要 owner 或 maintainer 权限。",
  "verification.accept": "需要 owner 或 maintainer 权限。",
};

export function canUseCapability(capabilities: SkillCapabilities | null, permission: SkillPermission) {
  return Boolean(capabilities?.permissions[permission]);
}

export function capabilityDeniedReason(permission: SkillPermission) {
  return permissionDeniedReasons[permission];
}

export function roleSummary(capabilities: SkillCapabilities | null) {
  if (!capabilities) return "当前角色 -";
  if (capabilities.roles.length === 0) return "当前角色 None";
  return `当前角色 ${capabilities.roles.map(roleLabel).join(" + ")}`;
}

export function roleLabel(role: string) {
  return role.charAt(0).toUpperCase() + role.slice(1);
}
