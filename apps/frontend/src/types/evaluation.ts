import type { ArtifactRef } from "./shared";
import type { SkillRecord, SkillVersion } from "./skill";

export type EvalSetSummary = {
  id: string;
  skill_id: string;
  name: string;
  description: string;
  created_at?: string;
  updated_at?: string;
};

export type EvalRunRecord = {
  id: string;
  skill_id: string;
  skill_version_id: string;
  eval_set_id: string;
  status: string;
  environment_tags: string[];
  run_context: Record<string, unknown>;
  run_context_hash: string;
  summary: { passed?: number; failed?: number; total?: number };
  result_artifact_id: string | null;
  created_at?: string;
  created_by: string;
};

export type EvalCaseVersionDetail = {
  id: string;
  skill_id: string;
  case_id: string;
  version_number: number;
  workspace_artifact_id?: string | null;
  steps: EvalCaseStep[];
  runner_config: EvalRunnerConfig;
  notes: string | null;
  created_at?: string;
  created_by: string;
  workspace_artifact?: ArtifactRef | null;
};

export type EvalRunnerConfig = {
  timeout_seconds?: number | null;
};

export type OpencodeModelSelection = {
  provider_id: string;
  model_id: string;
};

export type OpencodeModelOption = {
  id: string;
  name: string;
  family: string;
  status: string;
  capabilities: Record<string, unknown>;
  limit: Record<string, unknown>;
};

export type OpencodeProviderOption = {
  id: string;
  name: string;
  source: string;
  default_model_id?: string | null;
  models: OpencodeModelOption[];
};

export type OpencodeProviderCatalog = {
  providers: OpencodeProviderOption[];
};

export type EvalCaseStep = {
  id: string;
  title: string;
  input: string;
  assertions: EvalStepAssertion[];
};

export type EvalStepAssertion = {
  id: string;
  assertion_template_id: string;
  assertion_params: Record<string, unknown>;
};

export type EvalSetCase = {
  position: number;
  case: {
    id: string;
    skill_id: string;
    title: string;
    current_version_id: string | null;
    created_at?: string;
    updated_at?: string;
  };
  case_version: EvalCaseVersionDetail;
};

export type EvalCaseLibraryItem = {
  case: EvalSetCase["case"];
  case_version: EvalCaseVersionDetail;
};

export type EvalSetDetail = {
  eval_set: EvalSetSummary;
  cases: EvalSetCase[];
};

export type EvalAssertionTemplate = {
  id: string;
  name: string;
  description: string;
  category: string;
  params_schema: Array<{
    name: string;
    label: string;
    type: "text" | "textarea" | "number";
    required: boolean;
    default?: unknown;
    placeholder?: string;
    help?: string;
    min?: number | null;
    max?: number | null;
  }>;
};

export type EvalCaseRunRecord = {
  eval_case_run_id: string;
  job_id: string;
  skill_id: string;
  skill_version_id: string;
  eval_set_id: string;
  case_version_id: string;
  status: string;
  run_context_hash: string;
  passed?: boolean | null;
  score?: number | null;
};

export type EvalCaseRunDetail = {
  eval_case_run: {
    id: string;
    job_id: string;
    skill_id: string;
    skill_version_id: string;
    eval_set_id: string;
    case_version_id: string;
    status: string;
    passed?: boolean | null;
    score?: number | null;
    error?: string | null;
    runner_metadata?: Record<string, unknown>;
    run_context?: Record<string, unknown>;
    created_at?: string;
    started_at?: string | null;
    finished_at?: string | null;
  };
  job: { id: string; attempts: number; status: string; error?: string | null } | null;
  case_version: EvalCaseVersionDetail;
  result_artifact: ArtifactRef | null;
};

export type EvalCaseMutationResult = {
  skill_id: string;
  eval_set_id: string;
  eval_case_id: string;
  eval_case_version_id: string;
};

export type EvalCaseHistory = {
  case: EvalSetCase["case"];
  versions: Array<{
    case_version: EvalCaseVersionDetail;
    included_in_eval_sets: Array<{
      eval_set_id: string;
      name: string;
      position: number;
      created_at?: string;
    }>;
  }>;
};

export type EvalRunContext = {
  eval_run: EvalRunRecord;
  skill_version: SkillVersion;
  eval_set: EvalSetSummary;
  accepted_verification?: unknown | null;
};

export type EvalRunHistory = {
  skill: SkillRecord;
  runs: EvalRunContext[];
};

export type EvalRunDetail = {
  eval_run: EvalRunRecord;
  skill: SkillRecord;
  skill_version: SkillVersion;
  eval_set: EvalSetSummary;
  case_results: Array<{
    position: number;
    result: {
      run_id: string;
      case_version_id: string;
      passed: boolean;
      score?: number;
      created_at?: string;
    };
    result_artifact: ArtifactRef | null;
    case: EvalSetCase["case"];
    case_version: EvalCaseVersionDetail;
  }>;
};
