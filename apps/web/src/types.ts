export type ContentRef = {
  kind: string;
  locator: string;
  digest: string;
  path?: string | null;
};

export type SessionInfo = {
  actor: string;
  subject_type: string;
};

export type BundleFile = {
  path: string;
  sha256?: string;
  size_bytes?: number;
  content_text?: string | null;
  content_base64?: string | null;
  binary?: boolean;
};

export type SkillVersion = {
  id: string;
  skill_id: string;
  version_number: number;
  version: string;
  display_name?: string | null;
  content_ref: ContentRef;
  content_digest: string;
  change_summary: string;
  created_at?: string;
  created_by: string;
  bundle_artifact?: ArtifactRef;
  bundle_files?: BundleFile[];
};

export type EvalSetSummary = {
  id: string;
  skill_id: string;
  name: string;
  description: string;
  lifecycle_status: string;
  created_at?: string;
  updated_at?: string;
};

export type SkillRecord = {
  id: string;
  slug: string;
  owner_ref: string;
  current_version_id: string | null;
  lifecycle_status: string;
  created_at?: string;
  updated_at?: string;
};

export type EvalRunRecord = {
  id: string;
  skill_id: string;
  skill_version_id: string;
  eval_set_id: string;
  strategy: string;
  status: string;
  environment_tags: string[];
  run_context: Record<string, unknown>;
  run_context_hash: string;
  summary: { passed?: number; failed?: number; total?: number };
  result_artifact_id: string | null;
  created_at?: string;
  created_by: string;
};

export type SkillSummary = {
  skill: SkillRecord;
  summary: {
    skill: SkillRecord;
    current_version: SkillVersion | null;
    primary_eval_set: EvalSetSummary | null;
    latest_accepted_eval_run: EvalRunRecord | null;
  };
};

export type SkillDetail = {
  skill: SkillRecord;
  summary: SkillSummary["summary"];
  versions: SkillVersion[];
  eval_sets: EvalSetSummary[];
  latest_eval_runs: EvalRunRecord[];
  role_assignments: unknown[];
  audit_events: unknown[];
};

export type ArtifactRef = {
  id: string;
  kind: string;
  namespace: string;
  locator: string;
  digest: string;
  media_type: string;
  size_bytes: number;
  content_text?: string | null;
  created_at?: string;
  created_by: string;
};

export type EvalCaseVersionDetail = {
  id: string;
  skill_id: string;
  case_id: string;
  version_number: number;
  input_artifact_id: string;
  expected_output_artifact_id: string;
  attachment_artifact_id?: string | null;
  notes: string | null;
  created_at?: string;
  created_by: string;
  input_artifact: ArtifactRef;
  expected_output_artifact: ArtifactRef;
  attachment_artifact?: ArtifactRef | null;
};

export type EvalSetCase = {
  position: number;
  case: {
    id: string;
    skill_id: string;
    title: string;
    current_version_id: string | null;
    lifecycle_status: string;
    created_at?: string;
    updated_at?: string;
  };
  case_version: EvalCaseVersionDetail;
};

export type EvalSetDetail = {
  eval_set: EvalSetSummary;
  cases: EvalSetCase[];
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

export type ManualEvalResultPayload = {
  passed: boolean;
  actual_output: string;
};

export type BundleDiffStatus = "added" | "changed" | "removed" | "unchanged";

export type BundleDiffLine = {
  kind: "context" | "added" | "removed";
  old_line: number | null;
  new_line: number | null;
  text: string;
};

export type BundleDiffFile = {
  path: string;
  status: BundleDiffStatus;
  binary: boolean;
  left_digest: string | null;
  right_digest: string | null;
  left_size_bytes: number | null;
  right_size_bytes: number | null;
  hunks?: Array<{
    lines: BundleDiffLine[];
  }>;
};

export type BundleDiff = {
  left: {
    skill_version_id: string;
    version_number: number;
    version: string;
    content_digest: string;
  };
  right: {
    skill_version_id: string;
    version_number: number;
    version: string;
    content_digest: string;
  };
  summary: {
    added: number;
    changed: number;
    removed: number;
    unchanged: number;
    binary: number;
  };
  files: BundleDiffFile[];
};

export type BundleSource =
  | { kind: "files"; name: string; files: Array<{ path: string; content_text?: string; content_base64?: string }> }
  | { kind: "zip"; name: string; zip_base64: string };

export type ToastState = { tone: "success" | "danger" | "info"; message: string } | null;
