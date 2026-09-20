import { apiGet, apiSend } from "./httpClient";
import type { SkillDetail, SkillSummary, SkillVersion, RoleAssignment, TagGroup, ReviewRequest, PublishTarget, EvalRunHistory } from "../../types";

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };
export type SkillCore = Omit<SkillDetail, "versions"> & { version_count: number; highest_version: SkillVersion | null };
export type SkillPage = Page<SkillSummary> & { counts: Record<string, number>; tag_counts: Record<string, number> };
export type RoleSummary = RoleAssignment & { resource_label: string; resource_missing: boolean };
export type ReviewSummary = Pick<ReviewRequest, "id" | "skill_id" | "skill_version_id" | "status" | "summary" | "created_at" | "created_by" | "skill_version">;
export type ReviewPage = Page<ReviewSummary> & { counts: Record<string, number> };
export type AdminOverview = { counts: Record<string, number>; recent_tag_groups: Array<TagGroup & { value_count: number }>; recent_roles: RoleSummary[] };
export type GuidanceReview = Pick<ReviewRequest, "id" | "skill_version_id" | "status"> & { response_count: number; reviewer_count: number };
export type GuidancePublish = Pick<import("../../types").PublishRecord, "skill_version_id" | "status"> & { count: number };
export type Guidance = { versions: SkillVersion[]; reviews: GuidanceReview[]; publish_records: GuidancePublish[]; eval_runs: import("../../types").EvalRunRecord[] };

/** 编码分页过滤参数，省略未设置值。 */
export function queryString(params: Record<string, unknown>): string {
  return new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => [key, String(value)])).toString();
}

export const paginationApi = {
  skills: (params: Record<string, unknown>, signal?: AbortSignal, admin = false) =>
    apiSend<SkillPage>(`/api/${admin ? "admin/" : ""}skills/query`, "POST", params, { signal, admin }),
  core: (id: string) => apiGet<SkillCore>(`/api/skills/${id}/core`),
  versions: (id: string, params: Record<string, unknown>, signal?: AbortSignal) =>
    apiGet<Page<SkillVersion>>(`/api/skills/${id}/versions/page?${queryString(params)}`, { signal }),
  version: (id: string, signal?: AbortSignal, includeFiles = true) => apiGet<{ version: SkillVersion; previous: SkillVersion | null }>(`/api/skill-versions/${id}/detail?include_files=${includeFiles}`, { signal }),
  guidance: (id: string) => apiGet<Guidance>(`/api/skills/${id}/guidance`),
  reviews: (id: string, params: Record<string, unknown>, signal?: AbortSignal) =>
    apiGet<ReviewPage>(`/api/skills/${id}/reviews/page?${queryString(params)}`, { signal }),
  review: (id: string, signal?: AbortSignal) => apiGet<ReviewRequest>(`/api/reviews/${id}`, { signal }),
  targets: () => apiGet<PublishTarget[]>("/api/publish-targets/enabled"),
  runs: (id: string, params: Record<string, unknown>, signal?: AbortSignal) =>
    apiGet<Page<EvalRunHistory["runs"][number]>>(`/api/skills/${id}/eval-runs/page?${queryString(params)}`, { signal }),
  roles: (params: Record<string, unknown>, signal?: AbortSignal) =>
    apiGet<Page<RoleSummary>>(`/api/admin/role-assignments/page?${queryString(params)}`, { signal, admin: true }),
  overview: () => apiGet<AdminOverview>("/api/admin/overview", { admin: true }),
};
