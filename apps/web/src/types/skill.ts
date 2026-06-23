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
  tags: SkillTag[];
  created_at?: string;
  updated_at?: string;
};

export type SkillTag = {
  group_id: string;
  group_display_name?: string | null;
  value: string;
  value_display_name?: string | null;
};

export type SkillTagPayload = {
  group_id: string;
  value: string;
};

export type TagValueOption = {
  tag_group_id: string;
  value: string;
  display_name?: string | null;
  description: string;
  sort_order: number;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
};

export type TagGroup = {
  id: string;
  display_name: string;
  description: string;
  sort_order: number;
  values: TagValueOption[];
  created_at?: string;
  updated_at?: string;
  created_by?: string;
};

export type SkillRole = "viewer" | "evaluator" | "reviewer" | "maintainer" | "owner" | "admin";

export type RoleAssignment = {
  id: string;
  subject_type: "user" | "group";
  subject_id: string;
  resource_type: "skill" | "skill_tag";
  resource_id: string;
  role: SkillRole;
  created_at?: string;
  created_by: string;
};

export type SkillCapabilities = {
  actor: string;
  subject_type: string;
  groups: string[];
  roles: SkillRole[];
  effective_roles: SkillRole[];
  permissions: Record<string, boolean>;
  permission_sources: RoleAssignment[];
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
  role_assignments: RoleAssignment[];
  audit_events: unknown[];
  capabilities: SkillCapabilities | null;
};
