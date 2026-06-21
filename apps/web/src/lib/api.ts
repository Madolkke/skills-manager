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
  SessionInfo,
  SkillDetail,
  SkillSummary,
} from "../types";

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
};

function sessionApi() {
  return {
    getSession: () => apiGet<SessionInfo>("/api/session"),
  };
}

function skillApi() {
  return {
    listSkills: () => apiGet<SkillSummary[]>("/api/skills"),
    getSkill: (skillId: string) => apiGet<SkillDetail>(`/api/skills/${skillId}`),
    importSkill: (payload: { owner_ref: string; source: BundleSource; display_name?: string; version?: string }) =>
      apiSend<{ skill_id: string; skill_version_id: string }>("/api/skill-imports", "POST", payload),
    createSkillVersion: (payload: { skill_id: string; source: BundleSource; make_current?: boolean; display_name?: string; change_summary?: string; version?: string }) =>
      apiSend<{ skill_version_id: string }>("/api/skill-versions", "POST", payload),
    updateSkillVersionName: (versionId: string, displayName: string | null) =>
      apiSend<unknown>(`/api/skill-versions/${versionId}`, "PATCH", { display_name: displayName }),
  };
}

function artifactApi() {
  return {
    getBundleDiff: (leftSkillVersionId: string, rightSkillVersionId: string) =>
      apiGet<BundleDiff>(
        `/api/artifacts/diff?left_skill_version_id=${encodeURIComponent(leftSkillVersionId)}&right_skill_version_id=${encodeURIComponent(rightSkillVersionId)}`,
      ),
    artifactDownloadUrl: (artifactId: string) => `${API_BASE_URL}/api/artifacts/${encodeURIComponent(artifactId)}/download`,
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
    getEvalCaseHistory: (caseId: string) => apiGet<EvalCaseHistory>(`/api/eval-cases/${caseId}/versions`),
    listEvalCaseRuns: (query: { skill_version_id: string; eval_set_id: string }) =>
      apiGet<EvalCaseRunDetail[]>(
        `/api/eval-case-runs?skill_version_id=${encodeURIComponent(query.skill_version_id)}&eval_set_id=${encodeURIComponent(query.eval_set_id)}`,
      ),
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

async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    credentials: "include",
    headers: { accept: "application/json" },
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
