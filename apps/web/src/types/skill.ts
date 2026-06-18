import type { ArtifactRef, ContentRef } from "./shared";
import type { BundleFile } from "./bundle";
import type { EvalRunRecord, EvalSetSummary } from "./evaluation";

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

export type SkillRecord = {
  id: string;
  slug: string;
  owner_ref: string;
  current_version_id: string | null;
  lifecycle_status: string;
  created_at?: string;
  updated_at?: string;
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
