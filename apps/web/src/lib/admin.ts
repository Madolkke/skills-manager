import { encodeSkillTagResourceId, tagLabel } from "./skillTags";
import type { RoleAssignment, SkillSummary, TagGroup } from "../types";

export type AdminTab = "overview" | "groups" | "tag-groups" | "roles" | "skill-tags" | "publish-targets" | "publish";

export const ADMIN_TABS: Array<{ id: AdminTab; label: string }> = [
  { id: "overview", label: "概览" },
  { id: "groups", label: "用户组" },
  { id: "tag-groups", label: "Tag Group" },
  { id: "roles", label: "权限授权" },
  { id: "skill-tags", label: "Skill Tags" },
  { id: "publish-targets", label: "发布源" },
  { id: "publish", label: "发布确认" },
];

export function roleResourceLabel(role: RoleAssignment, tagGroups: TagGroup[], skills: SkillSummary[] = []): string {
  if (role.resource_type === "skill") {
    const skill = skills.find((item) => item.skill.id === role.resource_id);
    return skill ? `Skill: ${skill.skill.slug}` : `Skill: ${role.resource_id}`;
  }
  const tag = tagFromResourceId(role.resource_id, tagGroups);
  return tag ? `Skill Tag: ${tagLabel(tag, tagGroups)}` : `Skill Tag: ${role.resource_id}`;
}

export function tagFromResourceId(resourceId: string, tagGroups: TagGroup[]): { group_id: string; value: string; value_display_name?: string | null } | null {
  for (const group of tagGroups) {
    const value = group.values.find((item) => encodeSkillTagResourceId(group.id, item.value) === resourceId);
    if (value) return { group_id: group.id, value: value.value, value_display_name: value.display_name };
  }
  return null;
}

export function filterRoleAssignments(
  roles: RoleAssignment[],
  filters: { subject: string; resource: string; resourceType: string; role: string },
  tagGroups: TagGroup[],
  skills: SkillSummary[],
): RoleAssignment[] {
  const subject = filters.subject.trim().toLowerCase();
  const resource = filters.resource.trim().toLowerCase();
  return roles.filter((role) => {
    if (filters.resourceType && role.resource_type !== filters.resourceType) return false;
    if (filters.role && role.role !== filters.role) return false;
    if (subject && !`${role.subject_type}:${role.subject_id}`.toLowerCase().includes(subject)) return false;
    if (resource && !roleResourceLabel(role, tagGroups, skills).toLowerCase().includes(resource) && !role.resource_id.toLowerCase().includes(resource)) return false;
    return true;
  });
}

export function recentTagGroups(tagGroups: TagGroup[]): TagGroup[] {
  return [...tagGroups].sort((a, b) => (b.updated_at || b.created_at || "").localeCompare(a.updated_at || a.created_at || "")).slice(0, 5);
}
