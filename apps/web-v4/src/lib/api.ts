import type {
  BundleSource,
  BundleDiff,
  EvalCaseHistory,
  EvalCaseMutationResult,
  EvalRunDetail,
  EvalRunHistory,
  EvalSetVersionDetail,
  ManualEvalResultPayload,
  SessionInfo,
  SkillDetail,
  SkillSummary,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_SKILLHUB_API_URL ?? "http://127.0.0.1:8000";

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

export const api = {
  getSession: () => apiGet<SessionInfo>("/api/session"),
  listSkills: () => apiGet<SkillSummary[]>("/api/skills"),
  getSkill: (skillId: string) => apiGet<SkillDetail>(`/api/skills/${skillId}`),
  getEvalSetVersion: (versionId: string) => apiGet<EvalSetVersionDetail>(`/api/eval-set-versions/${versionId}`),
  getEvalCaseHistory: (caseId: string) => apiGet<EvalCaseHistory>(`/api/eval-cases/${caseId}/versions`),
  getEvalRunHistory: (skillId: string) => apiGet<EvalRunHistory>(`/api/skills/${skillId}/eval-runs`),
  getEvalRun: (runId: string) => apiGet<EvalRunDetail>(`/api/eval-runs/${runId}`),
  getBundleDiff: (leftSkillVersionId: string, rightSkillVersionId: string) =>
    apiGet<BundleDiff>(
      `/api/artifacts/diff?left_skill_version_id=${encodeURIComponent(leftSkillVersionId)}&right_skill_version_id=${encodeURIComponent(rightSkillVersionId)}`,
    ),
  importSkill: (payload: { owner_ref: string; source: BundleSource; display_name?: string }) =>
    apiSend<{ skill_id: string; skill_version_id: string }>("/api/skill-imports", "POST", payload),
  createSkillVersion: (payload: { skill_id: string; source: BundleSource; make_current?: boolean; display_name?: string }) =>
    apiSend<{ skill_version_id: string }>("/api/skill-versions", "POST", payload),
  updateSkillVersionName: (versionId: string, displayName: string | null) =>
    apiSend<unknown>(`/api/skill-versions/${versionId}`, "PATCH", { display_name: displayName }),
  updateEvalSetVersionName: (versionId: string, displayName: string | null) =>
    apiSend<unknown>(`/api/eval-set-versions/${versionId}`, "PATCH", { display_name: displayName }),
  createEvalCase: (payload: {
    skill_id: string;
    title: string;
    input_text: string;
    expected_output: string;
    notes?: string;
    eval_set_version_display_name?: string;
  }) => apiSend<EvalCaseMutationResult>("/api/eval-cases", "POST", payload),
  updateEvalCase: (
    caseId: string,
    payload: {
      title: string;
      input_text: string;
      expected_output: string;
      notes?: string;
      make_current: boolean;
      eval_set_version_display_name?: string;
    },
  ) => apiSend<EvalCaseMutationResult>(`/api/eval-cases/${caseId}`, "PATCH", { ...payload, case_id: caseId }),
  recordEvalRun: (payload: {
    skill_version_id: string;
    eval_set_version_id: string;
    strategy: string;
    environment_tags: string[];
    run_context: Record<string, unknown>;
    results: Record<string, ManualEvalResultPayload>;
  }) => apiSend<{ eval_run_id: string }>("/api/eval-runs", "POST", payload),
};

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: { accept: "application/json" },
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

async function apiSend<T>(path: string, method: "POST" | "PATCH", body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw await parseApiError(response);
  return response.json() as Promise<T>;
}

async function parseApiError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      field_errors?: Record<string, string> | Array<{ field?: string; message?: string }>;
    };
    const message = typeof payload.detail === "string" ? payload.detail : `${response.status} ${response.statusText}`;
    return new ApiError(message, response.status, normalizeFieldErrors(payload.field_errors));
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
