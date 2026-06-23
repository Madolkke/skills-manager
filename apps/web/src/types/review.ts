import type { SkillRecord, SkillVersion } from "./skill";

export type ReviewStatus = "open" | "closed" | "cancelled";
export type PublishRecordStatus = "pending_confirmation" | "released" | "cancelled" | "failed";
export type PublishGateCheckId =
  | "no_negative_score"
  | "no_neutral_score"
  | "all_reviewers_responded"
  | "min_responses"
  | "total_score_at_least"
  | "average_score_at_least"
  | "positive_ratio_at_least"
  | "negative_count_at_most";

export type PublishGateExpression =
  | { type: "group"; op: "and" | "or"; children: PublishGateExpression[] }
  | { type: "check"; check_id: PublishGateCheckId; params?: Record<string, unknown> };

export type PublishGateCheckDefinition = {
  id: PublishGateCheckId;
  label: string;
  description: string;
  params_schema: Array<{ name: string; label: string; type: "number"; min?: number; max?: number; step?: number; default?: number }>;
};

export type PublishTarget = {
  id: string;
  target_key: string;
  name: string;
  description: string;
  enabled: boolean;
  gate_expression: PublishGateExpression;
  config: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  created_by?: string;
};

export type ReviewReviewer = {
  review_request_id: string;
  skill_id: string;
  reviewer_actor: string;
  source_subject_type: "user" | "group";
  source_subject_id: string;
  created_at?: string;
};

export type ReviewResponse = {
  review_request_id: string;
  skill_id: string;
  reviewer_actor: string;
  score: -1 | 0 | 1;
  comment: string;
  created_at?: string;
  updated_at?: string;
};

export type ReviewCheckResult = {
  review_request_id?: string;
  skill_id?: string;
  check_id: string;
  label?: string;
  passed: boolean;
  details: Record<string, unknown>;
  required_params?: Record<string, unknown>;
  created_at?: string;
};

export type ReviewPublishTarget = {
  review_request_id: string;
  skill_id: string;
  publish_target_id: string;
  auto_submit_on_pass: boolean;
  target_key: string;
  name: string;
  description: string;
  enabled: boolean;
  gate_expression: PublishGateExpression;
  config: Record<string, unknown>;
  created_at?: string;
};

export type PublishRecord = {
  id: string;
  skill_id: string;
  skill_version_id: string;
  review_request_id: string;
  publish_target_id: string;
  status: PublishRecordStatus;
  check_snapshot: ReviewCheckResult[];
  metadata: Record<string, unknown>;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  created_at?: string;
  created_by: string;
  target_key?: string;
  target_name?: string;
  target_description?: string;
  target_enabled?: boolean;
  target_gate_expression?: PublishGateExpression;
  target_config?: Record<string, unknown>;
  skill?: SkillRecord;
  skill_version?: SkillVersion;
  publish_target?: PublishTarget;
  review?: ReviewRequest;
};

export type ReviewRequest = {
  id: string;
  skill_id: string;
  skill_version_id: string;
  status: ReviewStatus;
  summary: Record<string, unknown>;
  closed_at?: string | null;
  closed_by?: string | null;
  created_at?: string;
  created_by: string;
  skill: SkillRecord;
  skill_version: SkillVersion;
  reviewers: ReviewReviewer[];
  responses: ReviewResponse[];
  publish_targets: ReviewPublishTarget[];
  check_results: ReviewCheckResult[];
  publish_records: PublishRecord[];
};

export type SkillPublishOverview = {
  skill: SkillRecord;
  versions: Array<{ version: SkillVersion; review: ReviewRequest | null }>;
  publish_targets: PublishTarget[];
  publish_records: PublishRecord[];
};

export type NotificationItem = {
  id: string;
  recipient_actor_id: string;
  type: string;
  title: string;
  body: string;
  resource_type: string;
  resource_id: string;
  read_at?: string | null;
  created_at?: string;
  created_by: string;
};
