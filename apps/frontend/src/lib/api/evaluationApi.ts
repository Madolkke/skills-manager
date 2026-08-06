import type {
  EvalAssertionTemplate,
  EvalCaseHistory,
  EvalCaseLibraryItem,
  EvalCaseMutationResult,
  EvalCaseRunDetail,
  EvalCaseRunRecord,
  EvalCaseStep,
  EvalRunDetail,
  EvalRunHistory,
  EvalRunnerConfig,
  EvalSetDetail,
  EvalSetSummary,
  OpencodeAgentCatalog,
  OpencodeProviderCatalog,
} from "../../types";
import { apiDelete, apiGet, apiSend } from "./httpClient";

export function evaluationApi() {
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
