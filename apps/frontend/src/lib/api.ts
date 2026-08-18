import type {
  BundleDiff,
  BundleSource,
  CollectionDefinition,
  NotificationItem,
  PublishRecord,
  ReviewerCandidateOverview,
  ReviewRequest,
  ReviewSubject,
  RoleAssignment,
  SessionInfo,
  SkillBuilderCreateSessionPayload,
  SkillBuilderCreateSkillPayload,
  SkillBuilderDraftPayload,
  SkillBuilderMessagePayload,
  SkillBuilderSession,
  SkillBuilderWorkspacePayload,
  SkillCapabilities,
  SkillDetail,
  SkillPublishOverview,
  SkillSummary,
  SkillTagPayload,
  TagGroup,
  WorkflowCollectionChange,
  WorkflowDetail,
  WorkflowExpressionContract,
  WorkflowExpressionBatchItem,
  WorkflowExpressionBatchResponse,
  WorkflowExpressionEnvironment,
  WorkflowExpressionValidation,
  WorkflowMetadata,
  WorkflowSkillGeneratorCatalog,
  WorkflowSyncPayload,
  WorkflowSyncPreview,
  WorkflowSyncPreviewPayload,
  WorkflowSyncResult,
  WorkflowLogSchemaCatalog,
  WorkflowImportBundle,
  WorkflowImportDetail,
  CommandLibrarySearchResult,
} from "../types";
import { adminApi, type AdminGroup } from "./api/adminApi";
import { evaluationApi } from "./api/evaluationApi";
import { API_BASE_URL, apiDelete, apiDownload, apiDownloadBase64, apiGet, apiSend } from "./api/httpClient";

export type { AdminGroup } from "./api/adminApi";
export { ApiError, apiDelete, apiErrorMessage, apiGet, apiSend, resolveApiBaseUrl } from "./api/httpClient";

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
    importSkill: (payload: { owner_ref: string; source: BundleSource; version?: string; tags?: SkillTagPayload[] }) =>
      apiSend<{ skill_id: string; skill_version_id: string }>("/api/skill-imports", "POST", payload),
    createWorkflowSkill: (payload: { slug: string; owner_ref: string; description: string; tags?: SkillTagPayload[] }) =>
      apiSend<{ skill_id: string; skill_version_id: string; workflow_id: string }>("/api/workflows", "POST", payload),
    getWorkflow: (skillId: string) => apiGet<WorkflowDetail>(`/api/skills/${encodeURIComponent(skillId)}/workflow`),
    exportWorkflow: (skillId: string) =>
      apiGet<WorkflowImportBundle>(`/api/skills/${encodeURIComponent(skillId)}/workflow/export`),
    importWorkflow: (skillId: string, payload: unknown) =>
      apiSend<WorkflowImportDetail>(`/api/skills/${encodeURIComponent(skillId)}/workflow/import`, "POST", payload),
    saveWorkflow: (skillId: string, payload: { document: WorkflowDetail["document"]; collection_changes: WorkflowCollectionChange[] }) =>
      apiSend<WorkflowDetail>(`/api/skills/${encodeURIComponent(skillId)}/workflow`, "PUT", payload),
    updateWorkflowMetadata: (skillId: string, payload: WorkflowMetadata) =>
      apiSend<WorkflowDetail>(`/api/skills/${encodeURIComponent(skillId)}/workflow/metadata`, "PATCH", payload),
    listWorkflowCollections: (skillId: string) =>
      apiGet<{ definitions: CollectionDefinition[] }>(`/api/skills/${encodeURIComponent(skillId)}/workflow/collections`),
    searchCommandLibrary: (command: string, includeUser = false, targetVersion?: string, signal?: AbortSignal) =>
      apiSend<{ results: CommandLibrarySearchResult[] }>("/api/command-library/search", "POST", {
        command,
        includeUser,
        ...(targetVersion ? { targetVersion } : {}),
      }, { signal }),
    getWorkflowLogSchema: () => apiGet<WorkflowLogSchemaCatalog>("/api/workflow-log-schema"),
    listWorkflowSkillGenerators: () => apiGet<WorkflowSkillGeneratorCatalog>("/api/workflow-skill-generators"),
    previewWorkflowSync: (skillId: string, payload: WorkflowSyncPreviewPayload) =>
      apiSend<WorkflowSyncPreview>(`/api/skills/${encodeURIComponent(skillId)}/workflow/sync-preview`, "POST", payload),
    getWorkflowExpressionContract: () => apiGet<WorkflowExpressionContract>("/api/workflow-expression-contract"),
    validateWorkflowExpression: (source: string, environment: WorkflowExpressionEnvironment, signal?: AbortSignal) =>
      apiSend<WorkflowExpressionValidation>("/api/workflow-expression-validations", "POST", { source, environment }, { signal }),
    validateWorkflowExpressions: (expressions: WorkflowExpressionBatchItem[], environment: WorkflowExpressionEnvironment, signal?: AbortSignal) =>
      apiSend<WorkflowExpressionBatchResponse>("/api/workflow-expression-validations/batch", "POST", { expressions, environment }, { signal }),
    syncWorkflow: (skillId: string, payload: WorkflowSyncPayload) =>
      apiSend<WorkflowSyncResult>(`/api/skills/${encodeURIComponent(skillId)}/workflow/sync`, "POST", payload),
    listSkillBuilderSessions: () => apiGet<SkillBuilderSession[]>("/api/skill-builder/sessions"),
    createSkillBuilderSession: (payload: SkillBuilderCreateSessionPayload) =>
      apiSend<SkillBuilderSession>("/api/skill-builder/sessions", "POST", payload),
    getSkillBuilderSession: (sessionId: string) => apiGet<SkillBuilderSession>(`/api/skill-builder/sessions/${encodeURIComponent(sessionId)}`),
    sendSkillBuilderMessage: (sessionId: string, payload: SkillBuilderMessagePayload) =>
      apiSend<SkillBuilderSession>(`/api/skill-builder/sessions/${encodeURIComponent(sessionId)}/messages`, "POST", payload),
    updateSkillBuilderDraft: (sessionId: string, payload: SkillBuilderDraftPayload) =>
      apiSend<SkillBuilderSession>(`/api/skill-builder/sessions/${encodeURIComponent(sessionId)}/draft`, "PATCH", payload),
    updateSkillBuilderWorkspace: (sessionId: string, payload: SkillBuilderWorkspacePayload) =>
      apiSend<SkillBuilderSession>(`/api/skill-builder/sessions/${encodeURIComponent(sessionId)}/workspace`, "PATCH", payload),
    cancelSkillBuilderSession: (sessionId: string) =>
      apiSend<SkillBuilderSession>(`/api/skill-builder/sessions/${encodeURIComponent(sessionId)}/cancel`, "POST", {}),
    createSkillFromBuilder: (sessionId: string, payload: SkillBuilderCreateSkillPayload) =>
      apiSend<{ skill_id: string; skill_version_id: string; slug: string }>(`/api/skill-builder/sessions/${encodeURIComponent(sessionId)}/create-skill`, "POST", payload),
    createSkillVersion: (payload: { skill_id: string; source: BundleSource; make_current?: boolean; display_name?: string; change_summary?: string; version?: string }) =>
      apiSend<{ skill_version_id: string }>("/api/skill-versions", "POST", payload),
    updateSkillVersionName: (versionId: string, displayName: string | null) =>
      apiSend<unknown>(`/api/skill-versions/${versionId}`, "PATCH", { display_name: displayName }),
    updateSkill: (skillId: string, payload: { slug: string; owner_ref: string; tags?: SkillTagPayload[]; display_name?: string | null; expected_slug?: string }) =>
      apiSend<SkillDetail["skill"]>(`/api/skills/${encodeURIComponent(skillId)}`, "PATCH", payload),
    deleteSkill: (skillId: string, confirmationSlug: string) =>
      apiDelete<{ ok: boolean }>(`/api/skills/${encodeURIComponent(skillId)}`, {}, { confirmation_slug: confirmationSlug }),
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
    listReviewerCandidates: (skillId: string) => apiGet<ReviewerCandidateOverview>(`/api/skills/${encodeURIComponent(skillId)}/reviewer-candidates`),
    createReviewRequest: (skillId: string, payload: { skill_version_id: string; publish_targets: Array<{ publish_target_id: string; auto_submit_on_pass: boolean }>; reviewer_sources?: ReviewSubject[] }) =>
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
    downloadSkillBundle: (skillVersionId: string) => apiDownload(`/api/skill-versions/${encodeURIComponent(skillVersionId)}/download`),
    quickPublishSkillBundle: (skillVersionId: string) =>
      apiSend<{ destination: string; file_count: number }>(`/api/skill-versions/${encodeURIComponent(skillVersionId)}/quick-publish`, "POST", {}),
    downloadArtifactBase64: (artifactId: string) => apiDownloadBase64(`/api/artifacts/${encodeURIComponent(artifactId)}/download`),
  };
}
