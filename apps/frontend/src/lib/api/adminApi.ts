import type {
  OpencodeAgent,
  OpencodeAgentPayload,
  PublishGateCheckDefinition,
  PublishGateExpression,
  PublishRecord,
  PublishTarget,
  RoleAssignment,
  SkillDetail,
  SkillSummary,
  SkillTagPayload,
  TagCascadeOverview,
  TagGroup,
  WorkerStatusOverview,
  SystemCommand,
  ExpressionFunction,
  ExpressionFunctionPayload,
} from "../../types";
import { apiDelete, apiGet, apiSend } from "./httpClient";

export type AdminGroup = {
  id: string;
  scope_type: "global" | "skill";
  scope_id: string;
  name: string;
  description: string;
  members: Array<{ group_id: string; subject_type: string; subject_id: string }>;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
};

export function adminApi() {
  const options = { admin: true } as const;
  return {
    adminListSkills: () => apiGet<SkillSummary[]>("/api/admin/skills", options),
    adminUpdateSkill: (skillId: string, payload: { slug?: string; owner_ref?: string; tags?: SkillTagPayload[]; display_name?: string | null }) =>
      apiSend<SkillDetail["skill"]>(`/api/admin/skills/${encodeURIComponent(skillId)}`, "PATCH", payload, options),
    adminListGroups: () => apiGet<AdminGroup[]>("/api/admin/groups", options),
    adminCreateGroup: (payload: { name: string; description?: string }) => apiSend<AdminGroup>("/api/admin/groups", "POST", payload, options),
    adminUpdateGroup: (groupId: string, payload: { name: string; description?: string }) =>
      apiSend<AdminGroup>(`/api/admin/groups/${encodeURIComponent(groupId)}`, "PATCH", payload, options),
    adminDeleteGroup: (groupId: string) => apiDelete<{ ok: boolean }>(`/api/admin/groups/${encodeURIComponent(groupId)}`, options),
    adminAddGroupMember: (groupId: string, payload: { subject_id: string; subject_type?: string }) =>
      apiSend<AdminGroup>(`/api/admin/groups/${encodeURIComponent(groupId)}/members`, "POST", payload, options),
    adminRemoveGroupMember: (groupId: string, subjectId: string) =>
      apiDelete<AdminGroup>(`/api/admin/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(subjectId)}`, options),
    adminListTagGroups: () => apiGet<TagGroup[]>("/api/admin/tag-groups", options),
    adminCreateTagGroup: (payload: { id: string; display_name: string; description?: string; sort_order?: number; required?: boolean; free_form?: boolean; display_mode?: "checkbox" | "multi_select" }) =>
      apiSend<TagGroup>("/api/admin/tag-groups", "POST", payload, options),
    adminUpdateTagGroup: (groupId: string, payload: { display_name: string; description?: string; sort_order?: number; required?: boolean; free_form?: boolean; display_mode?: "checkbox" | "multi_select" }) =>
      apiSend<TagGroup>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}`, "PATCH", payload, options),
    adminDeleteTagGroup: (groupId: string) => apiDelete<{ ok: boolean }>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}`, options),
    adminCreateTagValue: (groupId: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }) =>
      apiSend<TagGroup>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}/values`, "POST", payload, options),
    adminUpdateTagValue: (groupId: string, value: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }) =>
      apiSend<TagGroup>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}/values/${encodeURIComponent(value)}`, "PATCH", payload, options),
    adminDeleteTagValue: (groupId: string, value: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}/values/${encodeURIComponent(value)}`, options),
    adminListTagCascades: () => apiGet<TagCascadeOverview>("/api/admin/tag-cascades", options),
    adminCreateTagCascade: (payload: { parent_group_id: string; parent_value?: string | null; child_group_id: string; activation_mode?: "parent_value" | "parent_selected" }) =>
      apiSend<TagCascadeOverview>("/api/admin/tag-cascades", "POST", payload, options),
    adminDeleteTagCascade: (childGroupId: string) => apiDelete<TagCascadeOverview>(`/api/admin/tag-cascades/${encodeURIComponent(childGroupId)}`, options),
    adminListRoleAssignments: () => apiGet<RoleAssignment[]>("/api/admin/role-assignments", options),
    adminAssignRole: (payload: { subject_type: "user" | "group"; subject_id: string; resource_type: "skill" | "skill_tag" | "global"; resource_id: string; role: string }) =>
      apiSend<RoleAssignment>("/api/admin/role-assignments", "POST", payload, options),
    adminDeleteRoleAssignment: (roleAssignmentId: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/role-assignments/${encodeURIComponent(roleAssignmentId)}`, options),
    adminListPublishTargets: () => apiGet<PublishTarget[]>("/api/admin/publish-targets", options),
    adminListPublishGateChecks: () => apiGet<PublishGateCheckDefinition[]>("/api/admin/publish-gate-checks", options),
    adminUpdatePublishTarget: (targetId: string, payload: { enabled: boolean; auto_publish_enabled: boolean; gate_expression: PublishGateExpression }) =>
      apiSend<PublishTarget>(`/api/admin/publish-targets/${encodeURIComponent(targetId)}`, "PATCH", payload, options),
    adminListPublishRecords: () => apiGet<PublishRecord[]>("/api/admin/publish-records", options),
    adminListWorkers: () => apiGet<WorkerStatusOverview>("/api/admin/workers", options),
    adminConfirmPublishRecord: (recordId: string) =>
      apiSend<PublishRecord>(`/api/admin/publish-records/${encodeURIComponent(recordId)}/confirm`, "POST", {}, options),
    adminCancelPublishRecord: (recordId: string) =>
      apiSend<PublishRecord>(`/api/admin/publish-records/${encodeURIComponent(recordId)}/cancel`, "POST", {}, options),
    adminRetryPublishRecord: (recordId: string) =>
      apiSend<PublishRecord>(`/api/admin/publish-records/${encodeURIComponent(recordId)}/retry`, "POST", {}, options),
    adminListOpencodeAgents: () => apiGet<OpencodeAgent[]>("/api/admin/opencode-agents", options),
    adminCreateOpencodeAgent: (payload: OpencodeAgentPayload) => apiSend<OpencodeAgent>("/api/admin/opencode-agents", "POST", payload, options),
    adminUpdateOpencodeAgent: (agentId: string, payload: OpencodeAgentPayload) =>
      apiSend<OpencodeAgent>(`/api/admin/opencode-agents/${encodeURIComponent(agentId)}`, "PATCH", payload, options),
    adminDeleteOpencodeAgent: (agentId: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/opencode-agents/${encodeURIComponent(agentId)}`, options),
    adminListSystemCommands: () => apiGet<{ commands: SystemCommand[] }>("/api/admin/system-commands", options),
    adminGetSystemCommand: (commandId: string) => apiGet<SystemCommand>(`/api/admin/system-commands/${encodeURIComponent(commandId)}`, options),
    adminCreateSystemCommand: (payload: Record<string, unknown>) => apiSend<SystemCommand>("/api/admin/system-commands", "POST", payload, options),
    adminUpdateSystemCommand: (commandId: string, payload: Record<string, unknown>) => apiSend<SystemCommand>(`/api/admin/system-commands/${encodeURIComponent(commandId)}`, "PUT", payload, options),
    adminDeleteSystemCommand: (commandId: string) => apiDelete<{ id: string; deleted: boolean }>(`/api/admin/system-commands/${encodeURIComponent(commandId)}`, options),
    adminListExpressionFunctions: () => apiGet<ExpressionFunction[]>("/api/admin/expression-functions", options),
    adminGetExpressionFunction: (functionId: string) => apiGet<ExpressionFunction>(`/api/admin/expression-functions/${encodeURIComponent(functionId)}`, options),
    adminCreateExpressionFunction: (payload: ExpressionFunctionPayload) => apiSend<ExpressionFunction>("/api/admin/expression-functions", "POST", payload, options),
    adminUpdateExpressionFunction: (functionId: string, payload: ExpressionFunctionPayload) => apiSend<ExpressionFunction>(`/api/admin/expression-functions/${encodeURIComponent(functionId)}`, "PUT", payload, options),
    adminDeleteExpressionFunction: (functionId: string) => apiDelete<{ id: string; deleted: boolean }>(`/api/admin/expression-functions/${encodeURIComponent(functionId)}`, options),
  };
}
