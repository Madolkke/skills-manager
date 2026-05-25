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

export type VariantVersion = {
  id: string;
  skill_id: string;
  variant_id: string;
  version_number: number;
  content_ref: ContentRef;
  content_digest: string;
  change_summary: string;
  created_at?: string;
  created_by: string;
  bundle_files?: BundleFile[];
};

export type VariantDetail = {
  id: string;
  skill_id: string;
  name: string;
  label: string;
  summary: string;
  tag_set_id: string;
  current_version_id: string | null;
  lifecycle_status: string;
  created_at?: string;
  updated_at?: string;
  tags: string[];
  current_version: VariantVersion | null;
  versions: VariantVersion[];
};

export type EvalSetVersion = {
  id: string;
  skill_id: string;
  eval_set_id: string;
  version_number: number;
  created_at?: string;
  created_by: string;
};

export type EvalSetSummary = {
  id: string;
  skill_id: string;
  name: string;
  description: string;
  current_version_id: string | null;
  lifecycle_status: string;
  created_at?: string;
  updated_at?: string;
  current_version: EvalSetVersion | null;
  versions: EvalSetVersion[];
};

export type SkillRecord = {
  id: string;
  slug: string;
  owner_ref: string;
  default_variant_id: string | null;
  lifecycle_status: string;
  created_at?: string;
  updated_at?: string;
};

export type EvalRunRecord = {
  id: string;
  skill_id: string;
  variant_version_id: string;
  eval_set_version_id: string;
  strategy: string;
  status: string;
  summary: { passed?: number; failed?: number; total?: number };
  result_artifact_id: string | null;
  created_at?: string;
  created_by: string;
};

export type SkillSummary = {
  skill: SkillRecord;
  default_variant: VariantDetail | null;
  primary_eval_set: EvalSetSummary | null;
  latest_accepted_eval_run: EvalRunRecord | null;
};

export type SkillDetail = {
  skill: SkillRecord;
  summary: SkillSummary;
  variants: VariantDetail[];
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
  notes: string | null;
  created_at?: string;
  created_by: string;
  input_artifact: ArtifactRef;
  expected_output_artifact: ArtifactRef;
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

export type EvalSetVersionDetail = {
  eval_set_version: EvalSetVersion;
  eval_set: Omit<EvalSetSummary, "current_version" | "versions">;
  cases: EvalSetCase[];
};

export type EvalCaseHistory = {
  case: EvalSetCase["case"];
  versions: Array<{
    case_version: EvalCaseVersionDetail;
    included_in_eval_set_versions: Array<{
      id: string;
      eval_set_id: string;
      version_number: number;
      position: number;
      created_at?: string;
      created_by: string;
    }>;
  }>;
};

export type EvalRunContext = {
  eval_run: EvalRunRecord;
  variant: VariantDetail;
  variant_version: VariantVersion;
  eval_set: Omit<EvalSetSummary, "current_version" | "versions">;
  eval_set_version: EvalSetVersion;
  accepted_verification?: unknown | null;
};

export type EvalRunHistory = {
  skill: SkillRecord;
  runs: EvalRunContext[];
};

export type EvalRunDetail = {
  eval_run: EvalRunRecord;
  skill: SkillRecord;
  variant_version: VariantVersion;
  eval_set_version: EvalSetVersion;
  case_results: Array<{
    result: {
      id: string;
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
    variant_version_id: string;
    version_number: number;
    content_digest: string;
  };
  right: {
    variant_version_id: string;
    version_number: number;
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

export type ToastState = {
  tone: "success" | "danger" | "info";
  message: string;
} | null;
