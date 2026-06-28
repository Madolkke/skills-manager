import type {
  BundleSource,
  BundleDiff,
  EvalCaseHistory,
  EvalCaseLibraryItem,
  EvalCaseRunRecord,
  EvalCaseRunDetail,
  EvalCaseMutationResult,
  EvalAssertionTemplate,
  EvalCaseStep,
  EvalRunnerConfig,
  EvalRunDetail,
  EvalRunHistory,
  EvalSetDetail,
  EvalSetSummary,
  OpencodeAgent,
  OpencodeAgentCatalog,
  OpencodeAgentPayload,
  OpencodeProviderCatalog,
  RoleAssignment,
  SessionInfo,
  SkillCapabilities,
  SkillDetail,
  SkillPublishOverview,
  SkillTagPayload,
  SkillSummary,
  TagGroup,
  NotificationItem,
  PublishRecord,
  PublishGateCheckDefinition,
  PublishGateExpression,
  PublishTarget,
  ReviewRequest,
} from "../types";
import { getActorId } from "./identity";

const API_BASE_URL = resolveApiBaseUrl({
  configuredUrl: import.meta.env.VITE_SKILLHUB_API_URL,
  configuredPort: import.meta.env.VITE_SKILLHUB_API_PORT,
  location: typeof window === "undefined" ? undefined : window.location,
});

type ApiBaseUrlInput = {
  configuredUrl?: string;
  configuredPort?: string;
  location?: Pick<Location, "protocol" | "hostname">;
};

export function resolveApiBaseUrl({ configuredUrl, configuredPort, location }: ApiBaseUrlInput): string {
  const explicitUrl = configuredUrl?.trim();
  if (explicitUrl) return explicitUrl.replace(/\/+$/, "");

  const port = configuredPort?.trim() || "8000";
  const protocol = location?.protocol === "https:" ? "https:" : "http:";
  const hostname = location?.hostname || "127.0.0.1";
  return `${protocol}//${hostname}:${port}`;
}

export class ApiError extends Error {
  readonly fieldErrors: Record<string, string>;
  readonly status: number;

  constructor(message: string, status: number, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

export function apiErrorMessage(error: ApiError): string {
  const messages = Object.values(error.fieldErrors).filter(Boolean);
  if (messages.length) return messages.join("；");
  return error.message;
}

export const api = {
  ...sessionApi(),
  ...skillApi(),
  ...artifactApi(),
  ...evaluationApi(),
  ...adminApi(),
};

function sessionApi() {
  return {
    getSession: () => apiGet<SessionInfo>("/api/session"),
  };
}

function skillApi() {
  return {
    listSkills: () => apiGet<SkillSummary[]>("/api/skills"),
    listTagGroups: () => apiGet<TagGroup[]>("/api/tag-groups"),
    getSkill: (skillId: string) => apiGet<SkillDetail>(`/api/skills/${skillId}`),
    importSkill: (payload: { owner_ref: string; source: BundleSource; display_name?: string; version?: string; tags?: SkillTagPayload[] }) =>
      apiSend<{ skill_id: string; skill_version_id: string }>("/api/skill-imports", "POST", payload),
    createSkillVersion: (payload: { skill_id: string; source: BundleSource; make_current?: boolean; display_name?: string; change_summary?: string; version?: string }) =>
      apiSend<{ skill_version_id: string }>("/api/skill-versions", "POST", payload),
    updateSkillVersionName: (versionId: string, displayName: string | null) =>
      apiSend<unknown>(`/api/skill-versions/${versionId}`, "PATCH", { display_name: displayName }),
    updateSkill: (skillId: string, payload: { slug: string; owner_ref: string; tags?: SkillTagPayload[] }) =>
      apiSend<SkillDetail["skill"]>(`/api/skills/${encodeURIComponent(skillId)}`, "PATCH", payload),
    getSkillCapabilities: (skillId: string) => apiGet<SkillCapabilities>(`/api/skills/${encodeURIComponent(skillId)}/capabilities`),
    listSkillGroups: (skillId: string) => apiGet<AdminGroup[]>(`/api/skills/${encodeURIComponent(skillId)}/groups`),
    createSkillGroup: (skillId: string, payload: { name: string; description?: string }) =>
      apiSend<AdminGroup>(`/api/skills/${encodeURIComponent(skillId)}/groups`, "POST", payload),
    updateSkillGroup: (skillId: string, groupId: string, payload: { name: string; description?: string }) =>
      apiSend<AdminGroup>(`/api/skills/${encodeURIComponent(skillId)}/groups/${encodeURIComponent(groupId)}`, "PATCH", payload),
    deleteSkillGroup: (skillId: string, groupId: string) =>
      apiDelete<{ ok: boolean }>(`/api/skills/${encodeURIComponent(skillId)}/groups/${encodeURIComponent(groupId)}`),
    addSkillGroupMember: (skillId: string, groupId: string, payload: { subject_id: string; subject_type?: string }) =>
      apiSend<AdminGroup>(`/api/skills/${encodeURIComponent(skillId)}/groups/${encodeURIComponent(groupId)}/members`, "POST", payload),
    removeSkillGroupMember: (skillId: string, groupId: string, subjectId: string) =>
      apiDelete<AdminGroup>(`/api/skills/${encodeURIComponent(skillId)}/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(subjectId)}`),
    assignSkillRole: (skillId: string, payload: { subject_type: "user" | "group"; subject_id: string; role: string }) =>
      apiSend<RoleAssignment>(`/api/skills/${encodeURIComponent(skillId)}/role-assignments`, "POST", payload),
    listSkillReviews: (skillId: string) => apiGet<ReviewRequest[]>(`/api/skills/${encodeURIComponent(skillId)}/reviews`),
    createReviewRequest: (skillId: string, payload: { skill_version_id: string; publish_targets: Array<{ publish_target_id: string; auto_submit_on_pass: boolean }> }) =>
      apiSend<ReviewRequest>(`/api/skills/${encodeURIComponent(skillId)}/reviews`, "POST", payload),
    closeReview: (reviewId: string) => apiSend<ReviewRequest>(`/api/reviews/${encodeURIComponent(reviewId)}/close`, "POST", {}),
    submitReviewResponse: (reviewId: string, payload: { score: -1 | 0 | 1; comment: string }) =>
      apiSend<ReviewRequest>(`/api/reviews/${encodeURIComponent(reviewId)}/responses`, "POST", payload),
    listMyReviews: () => apiGet<ReviewRequest[]>("/api/me/reviews"),
    listMyNotifications: () => apiGet<NotificationItem[]>("/api/me/notifications"),
    updateNotification: (notificationId: string, payload: { read: boolean }) =>
      apiSend<NotificationItem>(`/api/notifications/${encodeURIComponent(notificationId)}`, "PATCH", payload),
    getSkillPublishOverview: (skillId: string) => apiGet<SkillPublishOverview>(`/api/skills/${encodeURIComponent(skillId)}/publish`),
    createPublishRecord: (skillId: string, payload: { skill_version_id: string; review_request_id: string; publish_target_id: string }) =>
      apiSend<PublishRecord>(`/api/skills/${encodeURIComponent(skillId)}/publish-records`, "POST", payload),
  };
}

function artifactApi() {
  return {
    getBundleDiff: (leftSkillVersionId: string, rightSkillVersionId: string) =>
      apiGet<BundleDiff>(
        `/api/artifacts/diff?left_skill_version_id=${encodeURIComponent(leftSkillVersionId)}&right_skill_version_id=${encodeURIComponent(rightSkillVersionId)}`,
      ),
    artifactDownloadUrl: (artifactId: string) => `${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}/download`,
    downloadArtifactBase64: async (artifactId: string) => {
      const response = await fetch(`${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}/download`, {
        credentials: "include",
        headers: requestHeaders(),
      });
      if (!response.ok) throw await parseApiError(response);
      return blobToBase64(await response.blob());
    },
  };
}

function evaluationApi() {
  return {
    getEvalSet: (evalSetId: string) => apiGet<EvalSetDetail>(`/api/eval-sets/${evalSetId}`),
    createEvalSet: (skillId: string, payload: { name: string; description?: string }) =>
      apiSend<EvalSetSummary>(`/api/skills/${encodeURIComponent(skillId)}/eval-sets`, "POST", payload),
    updateEvalSet: (evalSetId: string, payload: { name: string; description?: string }) =>
      apiSend<EvalSetSummary>(`/api/eval-sets/${encodeURIComponent(evalSetId)}`, "PATCH", payload),
    listSkillEvalCases: (skillId: string, excludeEvalSetId?: string | null) => {
      const params = new URLSearchParams();
      if (excludeEvalSetId) params.set("exclude_eval_set_id", excludeEvalSetId);
      const suffix = params.toString() ? `?${params.toString()}` : "";
      return apiGet<EvalCaseLibraryItem[]>(`/api/skills/${encodeURIComponent(skillId)}/eval-cases${suffix}`);
    },
    addEvalSetCase: (evalSetId: string, payload: { case_id: string; position?: number }) =>
      apiSend<EvalSetDetail>(`/api/eval-sets/${encodeURIComponent(evalSetId)}/cases`, "POST", payload),
    removeEvalSetCase: (evalSetId: string, caseId: string) =>
      apiDelete<EvalSetDetail>(`/api/eval-sets/${encodeURIComponent(evalSetId)}/cases/${encodeURIComponent(caseId)}`),
    reorderEvalSetCases: (evalSetId: string, caseIds: string[]) =>
      apiSend<EvalSetDetail>(`/api/eval-sets/${encodeURIComponent(evalSetId)}/cases/order`, "PATCH", { case_ids: caseIds }),
    listEvalAssertionTemplates: () => apiGet<EvalAssertionTemplate[]>("/api/eval-assertion-templates"),
    listOpencodeProviders: () => apiGet<OpencodeProviderCatalog>("/api/opencode/providers"),
    listOpencodeAgents: () => apiGet<OpencodeAgentCatalog>("/api/opencode/agents"),
    getEvalCaseHistory: (caseId: string) => apiGet<EvalCaseHistory>(`/api/eval-cases/${caseId}/versions`),
    listEvalCaseRuns: (query: { skill_version_id: string; eval_set_id: string; run_context?: Record<string, unknown> }) => {
      const params = new URLSearchParams({ skill_version_id: query.skill_version_id, eval_set_id: query.eval_set_id });
      if (query.run_context && Object.keys(query.run_context).length > 0) params.set("run_context", JSON.stringify(query.run_context));
      return apiGet<EvalCaseRunDetail[]>(`/api/eval-case-runs?${params.toString()}`);
    },
    getEvalCaseRun: (evalCaseRunId: string) => apiGet<EvalCaseRunDetail>(`/api/eval-case-runs/${encodeURIComponent(evalCaseRunId)}`),
    getEvalRunHistory: (skillId: string, evalSetId?: string | null) => {
      const params = new URLSearchParams();
      if (evalSetId) params.set("eval_set_id", evalSetId);
      const suffix = params.toString() ? `?${params.toString()}` : "";
      return apiGet<EvalRunHistory>(`/api/skills/${encodeURIComponent(skillId)}/eval-runs${suffix}`);
    },
    getEvalRun: (runId: string) => apiGet<EvalRunDetail>(`/api/eval-runs/${runId}`),
    createEvalCase: (payload: {
      skill_id: string;
      eval_set_id: string;
      title: string;
      steps: EvalCaseStep[];
      workspace_name?: string;
      workspace_base64?: string;
      runner_config?: EvalRunnerConfig;
      notes?: string;
    }) => apiSend<EvalCaseMutationResult>("/api/eval-cases", "POST", payload),
    updateEvalCase: (
      caseId: string,
      payload: {
        title: string;
        eval_set_id: string;
        steps: EvalCaseStep[];
        workspace_name?: string;
        workspace_base64?: string;
        preserve_workspace?: boolean;
        runner_config?: EvalRunnerConfig;
        notes?: string;
        make_current: boolean;
      },
    ) => apiSend<EvalCaseMutationResult>(`/api/eval-cases/${caseId}`, "PATCH", { ...payload, case_id: caseId }),
    enqueueEvalCaseRun: (payload: {
      skill_version_id: string;
      eval_set_id: string;
      case_version_id: string;
      environment_tags: string[];
      run_context: Record<string, unknown>;
    }) => apiSend<EvalCaseRunRecord>("/api/eval-case-runs", "POST", payload),
    aggregateEvalRun: (payload: {
      skill_version_id: string;
      eval_set_id: string;
      environment_tags: string[];
      run_context: Record<string, unknown>;
    }) => apiSend<{ eval_run_id: string }>("/api/eval-runs/aggregations", "POST", payload),
  };
}

function adminApi() {
  return {
    adminListSkills: () => apiGet<SkillSummary[]>("/api/admin/skills", { admin: true }),
    adminUpdateSkill: (skillId: string, payload: { slug?: string; owner_ref?: string; tags?: SkillTagPayload[] }) =>
      apiSend<SkillDetail["skill"]>(`/api/admin/skills/${encodeURIComponent(skillId)}`, "PATCH", payload, { admin: true }),
    adminListGroups: () => apiGet<AdminGroup[]>("/api/admin/groups", { admin: true }),
    adminCreateGroup: (payload: { name: string; description?: string }) => apiSend<AdminGroup>("/api/admin/groups", "POST", payload, { admin: true }),
    adminUpdateGroup: (groupId: string, payload: { name: string; description?: string }) =>
      apiSend<AdminGroup>(`/api/admin/groups/${encodeURIComponent(groupId)}`, "PATCH", payload, { admin: true }),
    adminDeleteGroup: (groupId: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/groups/${encodeURIComponent(groupId)}`, { admin: true }),
    adminAddGroupMember: (groupId: string, payload: { subject_id: string; subject_type?: string }) =>
      apiSend<AdminGroup>(`/api/admin/groups/${encodeURIComponent(groupId)}/members`, "POST", payload, { admin: true }),
    adminRemoveGroupMember: (groupId: string, subjectId: string) =>
      apiDelete<AdminGroup>(`/api/admin/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(subjectId)}`, { admin: true }),
    adminListTagGroups: () => apiGet<TagGroup[]>("/api/admin/tag-groups", { admin: true }),
    adminCreateTagGroup: (payload: { id: string; display_name: string; description?: string; sort_order?: number }) =>
      apiSend<TagGroup>("/api/admin/tag-groups", "POST", payload, { admin: true }),
    adminUpdateTagGroup: (groupId: string, payload: { display_name: string; description?: string; sort_order?: number }) =>
      apiSend<TagGroup>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}`, "PATCH", payload, { admin: true }),
    adminDeleteTagGroup: (groupId: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}`, { admin: true }),
    adminCreateTagValue: (groupId: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }) =>
      apiSend<TagGroup>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}/values`, "POST", payload, { admin: true }),
    adminUpdateTagValue: (groupId: string, value: string, payload: { value: string; display_name?: string | null; description?: string; sort_order?: number }) =>
      apiSend<TagGroup>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}/values/${encodeURIComponent(value)}`, "PATCH", payload, { admin: true }),
    adminDeleteTagValue: (groupId: string, value: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/tag-groups/${encodeURIComponent(groupId)}/values/${encodeURIComponent(value)}`, { admin: true }),
    adminListRoleAssignments: () => apiGet<RoleAssignment[]>("/api/admin/role-assignments", { admin: true }),
    adminAssignRole: (payload: { subject_type: "user" | "group"; subject_id: string; resource_type: "skill" | "skill_tag"; resource_id: string; role: string }) =>
      apiSend<RoleAssignment>("/api/admin/role-assignments", "POST", payload, { admin: true }),
    adminDeleteRoleAssignment: (roleAssignmentId: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/role-assignments/${encodeURIComponent(roleAssignmentId)}`, { admin: true }),
    adminListPublishTargets: () => apiGet<PublishTarget[]>("/api/admin/publish-targets", { admin: true }),
    adminListPublishGateChecks: () => apiGet<PublishGateCheckDefinition[]>("/api/admin/publish-gate-checks", { admin: true }),
    adminUpdatePublishTarget: (targetId: string, payload: { enabled: boolean; gate_expression: PublishGateExpression }) =>
      apiSend<PublishTarget>(`/api/admin/publish-targets/${encodeURIComponent(targetId)}`, "PATCH", payload, { admin: true }),
    adminListPublishRecords: () => apiGet<PublishRecord[]>("/api/admin/publish-records", { admin: true }),
    adminConfirmPublishRecord: (recordId: string) =>
      apiSend<PublishRecord>(`/api/admin/publish-records/${encodeURIComponent(recordId)}/confirm`, "POST", {}, { admin: true }),
    adminCancelPublishRecord: (recordId: string) =>
      apiSend<PublishRecord>(`/api/admin/publish-records/${encodeURIComponent(recordId)}/cancel`, "POST", {}, { admin: true }),
    adminListOpencodeAgents: () => apiGet<OpencodeAgent[]>("/api/admin/opencode-agents", { admin: true }),
    adminCreateOpencodeAgent: (payload: OpencodeAgentPayload) =>
      apiSend<OpencodeAgent>("/api/admin/opencode-agents", "POST", payload, { admin: true }),
    adminUpdateOpencodeAgent: (agentId: string, payload: OpencodeAgentPayload) =>
      apiSend<OpencodeAgent>(`/api/admin/opencode-agents/${encodeURIComponent(agentId)}`, "PATCH", payload, { admin: true }),
    adminDeleteOpencodeAgent: (agentId: string) =>
      apiDelete<{ ok: boolean }>(`/api/admin/opencode-agents/${encodeURIComponent(agentId)}`, { admin: true }),
  };
}

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

type RequestOptions = { admin?: boolean };

async function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: requestHeaders(options),
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

async function apiSend<T>(path: string, method: "POST" | "PATCH", body: unknown, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: requestHeaders({ ...options, json: true } as RequestOptions & { json: boolean }),
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

async function apiDelete<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    credentials: "include",
    headers: requestHeaders(options),
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

function requestHeaders(options: RequestOptions & { json?: boolean } = {}): HeadersInit {
  const headers: Record<string, string> = { accept: "application/json", "X-SkillHub-Actor": getActorId() };
  if (options.json) headers["content-type"] = "application/json";
  if (options.admin) {
    const key = typeof window === "undefined" ? "" : window.sessionStorage.getItem("skillhub.admin.key") || "";
    if (key) headers["X-SkillHub-Admin-Key"] = key;
  }
  return headers;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "");
    reader.onerror = () => reject(new Error("读取 artifact 失败。"));
    reader.readAsDataURL(blob);
  });
}

async function parseApiError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      field_errors?: Record<string, string> | Array<{ field?: string; message?: string }>;
    };
    const message = typeof payload.detail === "string" ? payload.detail : `${response.status} ${response.statusText}`;
    const error = new ApiError(message, response.status, normalizeFieldErrors(payload.field_errors));
    return new ApiError(apiErrorMessage(error), response.status, error.fieldErrors);
  } catch {
    return new ApiError(`${response.status} ${response.statusText}`, response.status);
  }
}

function normalizeFieldErrors(errors: unknown): Record<string, string> {
  if (!errors) return {};
  if (!Array.isArray(errors)) return errors as Record<string, string>;
  return Object.fromEntries(
    errors.map((item) => {
      const row = item as { field?: unknown; message?: unknown };
      return [typeof row.field === "string" ? row.field : "_form", String(row.message ?? "字段格式不正确。")];
    }),
  );
}
