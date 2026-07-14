from __future__ import annotations

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB


metadata = MetaData()

# This metadata backs application queries and PostgreSQL integration tests.
# Startup applies metadata first and then runs the idempotent patches in sync.py.
# schema.sql is the checked-in contract fixture used by schema tests and deployments.


def timestamp_column(name: str = "created_at") -> Column[DateTime]:
    return Column(name, DateTime(timezone=True), nullable=False, server_default=text("now()"))


artifacts = Table(
    "artifacts",
    metadata,
    Column("id", Text, primary_key=True),
    Column("kind", Text, nullable=False),
    Column("namespace", Text, nullable=False),
    Column("locator", Text, nullable=False),
    Column("digest", Text, nullable=False),
    Column("media_type", Text, nullable=False),
    Column("size_bytes", BigInteger, nullable=False, server_default=text("0")),
    Column("content_text", Text),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("size_bytes >= 0", name="artifacts_size_bytes_non_negative"),
    UniqueConstraint("locator", "digest", name="artifacts_locator_digest_unique"),
)

skills = Table(
    "skills",
    metadata,
    Column("id", Text, primary_key=True),
    Column("slug", Text, nullable=False),
    Column("owner_ref", Text, nullable=False),
    Column("current_version_id", Text),
    Column("lifecycle_status", Text, nullable=False, server_default=text("'active'")),
    timestamp_column(),
    timestamp_column("updated_at"),
    UniqueConstraint("slug", name="skills_slug_unique"),
    CheckConstraint("lifecycle_status in ('active', 'archived')", name="skills_lifecycle_status_check"),
)

skill_versions = Table(
    "skill_versions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("version", Text, nullable=False),
    Column("display_name", Text),
    Column("content_ref", JSONB(), nullable=False),
    Column("content_digest", Text, nullable=False),
    Column("change_summary", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("version_number > 0", name="skill_versions_version_number_positive"),
    CheckConstraint("version ~ '^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?(?:\\+([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?$'", name="skill_versions_version_semver_check"),
    UniqueConstraint("skill_id", "version_number", name="skill_versions_skill_version_unique"),
    UniqueConstraint("skill_id", "version", name="skill_versions_skill_semver_unique"),
    UniqueConstraint("id", "skill_id", name="skill_versions_id_skill_unique"),
)

skills.append_constraint(
    ForeignKeyConstraint(["current_version_id", "id"], ["skill_versions.id", "skill_versions.skill_id"], name="skills_current_version_fkey")
)

workflows = Table(
    "workflows",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("revision", Integer, nullable=False, server_default=text("1")),
    Column("document_schema_version", Integer, nullable=False, server_default=text("3")),
    Column("document", JSONB(), nullable=False),
    Column("document_digest", Text, nullable=False),
    timestamp_column(),
    timestamp_column("updated_at"),
    Column("created_by", Text, nullable=False),
    Column("last_saved_by", Text, nullable=False),
    CheckConstraint("revision > 0", name="workflows_revision_positive"),
    CheckConstraint("document_schema_version > 0", name="workflows_schema_version_positive"),
    CheckConstraint("jsonb_typeof(document) = 'object'", name="workflows_document_object"),
    UniqueConstraint("skill_id", name="workflows_skill_unique"),
)

workflow_collection_definitions = Table(
    "workflow_collection_definitions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("latest_revision", Integer, nullable=False, server_default=text("1")),
    timestamp_column(),
    timestamp_column("updated_at"),
    Column("created_by", Text, nullable=False),
    CheckConstraint("latest_revision > 0", name="workflow_collection_definitions_revision_positive"),
)

workflow_collection_revisions = Table(
    "workflow_collection_revisions",
    metadata,
    Column("definition_id", Text, ForeignKey("workflow_collection_definitions.id"), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("document_schema_version", Integer, nullable=False, server_default=text("3")),
    Column("definition", JSONB(), nullable=False),
    Column("definition_digest", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    PrimaryKeyConstraint("definition_id", "revision"),
    CheckConstraint("revision > 0", name="workflow_collection_revisions_revision_positive"),
    CheckConstraint("document_schema_version > 0", name="workflow_collection_revisions_schema_version_positive"),
    CheckConstraint("jsonb_typeof(definition) = 'object'", name="workflow_collection_revisions_definition_object"),
)

workflow_syncs = Table(
    "workflow_syncs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("workflow_id", Text, ForeignKey("workflows.id"), nullable=False),
    Column("workflow_revision", Integer, nullable=False),
    Column("document_schema_version", Integer, nullable=False),
    Column("source_artifact_id", Text, ForeignKey("artifacts.id"), nullable=False),
    Column("skill_version_id", Text, ForeignKey("skill_versions.id"), nullable=False),
    Column("generator_version", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("workflow_revision > 0", name="workflow_syncs_revision_positive"),
    CheckConstraint("document_schema_version > 0", name="workflow_syncs_schema_version_positive"),
    UniqueConstraint("workflow_id", "workflow_revision", name="workflow_syncs_workflow_revision_unique"),
    UniqueConstraint("skill_version_id", name="workflow_syncs_skill_version_unique"),
)

eval_sets = Table(
    "eval_sets",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=text("''")),
    timestamp_column(),
    timestamp_column("updated_at"),
    UniqueConstraint("id", "skill_id", name="eval_sets_id_skill_unique"),
    UniqueConstraint("skill_id", "name", name="eval_sets_skill_name_unique"),
)

eval_cases = Table(
    "eval_cases",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("title", Text, nullable=False),
    Column("current_version_id", Text),
    timestamp_column(),
    timestamp_column("updated_at"),
    UniqueConstraint("id", "skill_id", name="eval_cases_id_skill_unique"),
)

eval_case_versions = Table(
    "eval_case_versions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, nullable=False),
    Column("case_id", Text, nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("workspace_artifact_id", Text, ForeignKey("artifacts.id")),
    Column("steps", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
    Column("runner_config", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("notes", Text),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("jsonb_typeof(steps) = 'array'", name="eval_case_versions_steps_array"),
    CheckConstraint("jsonb_typeof(runner_config) = 'object'", name="eval_case_versions_runner_config_object"),
    CheckConstraint("version_number > 0", name="eval_case_versions_version_number_positive"),
    UniqueConstraint("case_id", "version_number", name="eval_case_versions_case_version_unique"),
    UniqueConstraint("id", "skill_id", name="eval_case_versions_id_skill_unique"),
    ForeignKeyConstraint(["case_id", "skill_id"], ["eval_cases.id", "eval_cases.skill_id"], name="eval_case_versions_case_skill_fkey"),
)

eval_cases.append_constraint(
    ForeignKeyConstraint(["current_version_id", "skill_id"], ["eval_case_versions.id", "eval_case_versions.skill_id"], name="eval_cases_current_version_fkey")
)

eval_set_cases = Table(
    "eval_set_cases",
    metadata,
    Column("eval_set_id", Text, nullable=False),
    Column("skill_id", Text, nullable=False),
    Column("case_id", Text, nullable=False),
    Column("position", Integer, nullable=False),
    PrimaryKeyConstraint("eval_set_id", "position"),
    CheckConstraint("position >= 0", name="eval_set_cases_position_non_negative"),
    UniqueConstraint("eval_set_id", "case_id", name="eval_set_cases_case_unique"),
    ForeignKeyConstraint(["eval_set_id", "skill_id"], ["eval_sets.id", "eval_sets.skill_id"], name="eval_set_cases_set_skill_fkey"),
    ForeignKeyConstraint(["case_id", "skill_id"], ["eval_cases.id", "eval_cases.skill_id"], name="eval_set_cases_case_skill_fkey"),
)

eval_runs = Table(
    "eval_runs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, nullable=False),
    Column("skill_version_id", Text, nullable=False),
    Column("eval_set_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("environment_tags", ARRAY(Text), nullable=False, server_default=text("'{}'")),
    Column("run_context", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("run_context_hash", Text, nullable=False),
    Column("summary", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("result_artifact_id", Text, ForeignKey("artifacts.id")),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("status in ('queued', 'running', 'finished', 'failed')", name="eval_runs_status_check"),
    UniqueConstraint("id", "skill_id", name="eval_runs_id_skill_unique"),
    ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="eval_runs_skill_version_skill_fkey"),
    ForeignKeyConstraint(["eval_set_id", "skill_id"], ["eval_sets.id", "eval_sets.skill_id"], name="eval_runs_eval_set_skill_fkey"),
)

case_results = Table(
    "case_results",
    metadata,
    Column("run_id", Text, nullable=False),
    Column("skill_id", Text, nullable=False),
    Column("case_version_id", Text, nullable=False),
    Column("passed", Boolean, nullable=False),
    Column("score", Integer, nullable=False),
    Column("result_artifact_id", Text, ForeignKey("artifacts.id")),
    timestamp_column(),
    PrimaryKeyConstraint("run_id", "case_version_id"),
    CheckConstraint("score in (0, 1)", name="case_results_score_pass_fail"),
    ForeignKeyConstraint(["run_id", "skill_id"], ["eval_runs.id", "eval_runs.skill_id"], name="case_results_run_skill_fkey"),
    ForeignKeyConstraint(["case_version_id", "skill_id"], ["eval_case_versions.id", "eval_case_versions.skill_id"], name="case_results_case_skill_fkey"),
)

eval_case_runs = Table(
    "eval_case_runs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("job_id", Text, ForeignKey("jobs.id")),
    Column("skill_id", Text, nullable=False),
    Column("skill_version_id", Text, nullable=False),
    Column("eval_set_id", Text, nullable=False),
    Column("case_version_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("environment_tags", ARRAY(Text), nullable=False, server_default=text("'{}'")),
    Column("run_context", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("run_context_hash", Text, nullable=False),
    Column("passed", Boolean),
    Column("score", Integer),
    Column("result_artifact_id", Text, ForeignKey("artifacts.id")),
    Column("runner_metadata", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    timestamp_column(),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("created_by", Text, nullable=False),
    Column("error", Text),
    CheckConstraint("status in ('queued', 'running', 'succeeded', 'failed', 'canceled')", name="eval_case_runs_status_check"),
    CheckConstraint("score is null or score in (0, 1)", name="eval_case_runs_score_pass_fail"),
    UniqueConstraint("id", "skill_id", name="eval_case_runs_id_skill_unique"),
    ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="eval_case_runs_skill_version_skill_fkey"),
    ForeignKeyConstraint(["eval_set_id", "skill_id"], ["eval_sets.id", "eval_sets.skill_id"], name="eval_case_runs_eval_set_skill_fkey"),
    ForeignKeyConstraint(["case_version_id", "skill_id"], ["eval_case_versions.id", "eval_case_versions.skill_id"], name="eval_case_runs_case_skill_fkey"),
)

accepted_verifications = Table(
    "accepted_verifications",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, nullable=False),
    Column("skill_version_id", Text, nullable=False),
    Column("eval_set_id", Text, nullable=False),
    Column("run_context_hash", Text, nullable=False),
    Column("eval_run_id", Text, nullable=False),
    Column("note", Text, nullable=False, server_default=text("''")),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    UniqueConstraint("id", "skill_id", name="accepted_verifications_id_skill_unique"),
    UniqueConstraint("skill_id", "skill_version_id", "eval_set_id", "run_context_hash", name="accepted_verifications_context_unique"),
    ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="accepted_verifications_skill_version_skill_fkey"),
    ForeignKeyConstraint(["eval_set_id", "skill_id"], ["eval_sets.id", "eval_sets.skill_id"], name="accepted_verifications_eval_set_skill_fkey"),
    ForeignKeyConstraint(["eval_run_id", "skill_id"], ["eval_runs.id", "eval_runs.skill_id"], name="accepted_verifications_eval_run_skill_fkey"),
)

review_requests = Table(
    "review_requests",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, nullable=False),
    Column("skill_version_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("summary", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("closed_at", DateTime(timezone=True)),
    Column("closed_by", Text),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("status in ('open', 'closed', 'cancelled')", name="review_requests_status_check"),
    UniqueConstraint("id", "skill_id", name="review_requests_id_skill_unique"),
    ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="review_requests_skill_version_skill_fkey"),
)

review_request_reviewers = Table(
    "review_request_reviewers",
    metadata,
    Column("review_request_id", Text, nullable=False),
    Column("skill_id", Text, nullable=False),
    Column("reviewer_actor", Text, nullable=False),
    Column("source_subject_type", Text, nullable=False),
    Column("source_subject_id", Text, nullable=False),
    timestamp_column(),
    PrimaryKeyConstraint("review_request_id", "reviewer_actor"),
    CheckConstraint("source_subject_type in ('user', 'group')", name="review_request_reviewers_source_type_check"),
    ForeignKeyConstraint(["review_request_id", "skill_id"], ["review_requests.id", "review_requests.skill_id"], name="review_request_reviewers_review_skill_fkey"),
)

review_responses = Table(
    "review_responses",
    metadata,
    Column("review_request_id", Text, nullable=False),
    Column("skill_id", Text, nullable=False),
    Column("reviewer_actor", Text, nullable=False),
    Column("score", Integer, nullable=False),
    Column("comment", Text, nullable=False, server_default=text("''")),
    timestamp_column(),
    timestamp_column("updated_at"),
    PrimaryKeyConstraint("review_request_id", "reviewer_actor"),
    CheckConstraint("score in (-1, 0, 1)", name="review_responses_score_check"),
    ForeignKeyConstraint(["review_request_id", "skill_id"], ["review_requests.id", "review_requests.skill_id"], name="review_responses_review_skill_fkey"),
    ForeignKeyConstraint(["review_request_id", "reviewer_actor"], ["review_request_reviewers.review_request_id", "review_request_reviewers.reviewer_actor"], name="review_responses_reviewer_fkey"),
)

publish_targets = Table(
    "publish_targets",
    metadata,
    Column("id", Text, primary_key=True),
    Column("target_key", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=text("''")),
    Column("enabled", Boolean, nullable=False, server_default=text("true")),
    Column("auto_publish_enabled", Boolean, nullable=False, server_default=text("false")),
    Column("gate_expression", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("config", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    timestamp_column(),
    timestamp_column("updated_at"),
    Column("created_by", Text, nullable=False),
    UniqueConstraint("target_key", name="publish_targets_key_unique"),
    CheckConstraint("length(btrim(target_key)) > 0", name="publish_targets_key_non_empty"),
    CheckConstraint("jsonb_typeof(gate_expression) = 'object'", name="publish_targets_gate_expression_object"),
    CheckConstraint("jsonb_typeof(config) = 'object'", name="publish_targets_config_object"),
)

review_request_publish_targets = Table(
    "review_request_publish_targets",
    metadata,
    Column("review_request_id", Text, nullable=False),
    Column("skill_id", Text, nullable=False),
    Column("publish_target_id", Text, ForeignKey("publish_targets.id"), nullable=False),
    Column("auto_submit_on_pass", Boolean, nullable=False, server_default=text("true")),
    timestamp_column(),
    PrimaryKeyConstraint("review_request_id", "publish_target_id"),
    ForeignKeyConstraint(["review_request_id", "skill_id"], ["review_requests.id", "review_requests.skill_id"], name="review_request_publish_targets_review_skill_fkey"),
)

review_check_results = Table(
    "review_check_results",
    metadata,
    Column("review_request_id", Text, nullable=False),
    Column("skill_id", Text, nullable=False),
    Column("check_id", Text, nullable=False),
    Column("passed", Boolean, nullable=False),
    Column("details", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    timestamp_column(),
    PrimaryKeyConstraint("review_request_id", "check_id"),
    ForeignKeyConstraint(["review_request_id", "skill_id"], ["review_requests.id", "review_requests.skill_id"], name="review_check_results_review_skill_fkey"),
)

publish_records = Table(
    "publish_records",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, nullable=False),
    Column("skill_version_id", Text, nullable=False),
    Column("review_request_id", Text, nullable=False),
    Column("publish_target_id", Text, ForeignKey("publish_targets.id"), nullable=False),
    Column("status", Text, nullable=False),
    Column("check_snapshot", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
    Column("metadata", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("confirmed_at", DateTime(timezone=True)),
    Column("confirmed_by", Text),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("status in ('pending_confirmation', 'released', 'cancelled', 'failed')", name="publish_records_status_check"),
    UniqueConstraint("skill_version_id", "publish_target_id", name="publish_records_version_target_unique"),
    UniqueConstraint("id", "skill_id", name="publish_records_id_skill_unique"),
    ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="publish_records_skill_version_skill_fkey"),
    ForeignKeyConstraint(["review_request_id", "skill_id"], ["review_requests.id", "review_requests.skill_id"], name="publish_records_review_skill_fkey"),
)

notifications = Table(
    "notifications",
    metadata,
    Column("id", Text, primary_key=True),
    Column("recipient_actor_id", Text, nullable=False),
    Column("type", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("body", Text, nullable=False, server_default=text("''")),
    Column("resource_type", Text, nullable=False),
    Column("resource_id", Text, nullable=False),
    Column("read_at", DateTime(timezone=True)),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
)

opencode_agents = Table(
    "opencode_agents",
    metadata,
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=text("''")),
    Column("prompt", Text, nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("true")),
    Column("deleted_at", DateTime(timezone=True)),
    Column("permission", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("provider_id", Text),
    Column("model_id", Text),
    Column("temperature", Text),
    Column("steps", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
    timestamp_column(),
    timestamp_column("updated_at"),
    Column("created_by", Text, nullable=False),
    Column("updated_by", Text, nullable=False),
    CheckConstraint("id ~ '^[A-Za-z0-9_-]+$'", name="opencode_agents_id_format_check"),
    CheckConstraint("length(btrim(name)) > 0", name="opencode_agents_name_non_empty"),
    CheckConstraint("length(btrim(prompt)) > 0", name="opencode_agents_prompt_non_empty"),
    CheckConstraint("jsonb_typeof(permission) = 'object'", name="opencode_agents_permission_object"),
    CheckConstraint("jsonb_typeof(steps) = 'array'", name="opencode_agents_steps_array"),
)

skill_builder_sessions = Table(
    "skill_builder_sessions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("actor_ref", Text, nullable=False),
    Column("title", Text, nullable=False, server_default=text("''")),
    Column("status", Text, nullable=False, server_default=text("'active'")),
    Column("opencode_session_id", Text),
    Column("workdir", Text),
    Column("draft_files", JSONB(), nullable=False, server_default=text("'[]'::jsonb")),
    Column("run_selection", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_skill_id", Text, ForeignKey("skills.id")),
    Column("created_skill_version_id", Text, ForeignKey("skill_versions.id")),
    Column("last_error", Text),
    timestamp_column(),
    timestamp_column("updated_at"),
    CheckConstraint("status in ('active', 'running', 'draft_ready', 'created', 'failed')", name="skill_builder_sessions_status_check"),
    CheckConstraint("jsonb_typeof(draft_files) = 'array'", name="skill_builder_sessions_draft_files_array"),
    CheckConstraint("jsonb_typeof(run_selection) = 'object'", name="skill_builder_sessions_run_selection_object"),
)

skill_builder_messages = Table(
    "skill_builder_messages",
    metadata,
    Column("id", Text, primary_key=True),
    Column("session_id", Text, ForeignKey("skill_builder_sessions.id"), nullable=False),
    Column("role", Text, nullable=False),
    Column("intent", Text, nullable=False, server_default=text("'chat'")),
    Column("content", Text, nullable=False, server_default=text("''")),
    Column("metadata", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    Column("job_id", Text, ForeignKey("jobs.id")),
    timestamp_column(),
    CheckConstraint("role in ('user', 'assistant', 'system')", name="skill_builder_messages_role_check"),
    CheckConstraint("intent in ('chat', 'generate_draft')", name="skill_builder_messages_intent_check"),
    CheckConstraint("jsonb_typeof(metadata) = 'object'", name="skill_builder_messages_metadata_object"),
)

saved_views = Table(
    "saved_views",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("view_type", Text, nullable=False),
    Column("config", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("view_type in ('run_history')", name="saved_views_type_check"),
    UniqueConstraint("skill_id", "view_type", "name", name="saved_views_skill_type_name_unique"),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("type", Text, nullable=False),
    Column("status", Text, nullable=False, server_default=text("'queued'")),
    Column("payload", JSONB(), nullable=False),
    Column("result_ref", Text),
    Column("attempts", Integer, nullable=False, server_default=text("0")),
    Column("locked_by", Text),
    Column("last_heartbeat_at", DateTime(timezone=True)),
    timestamp_column(),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("created_by", Text, nullable=False),
    Column("error", Text),
    CheckConstraint("status in ('queued', 'running', 'succeeded', 'failed', 'canceled')", name="jobs_status_check"),
)

worker_heartbeats = Table(
    "worker_heartbeats",
    metadata,
    Column("worker_id", Text, primary_key=True),
    Column("status", Text, nullable=False, server_default=text("'idle'")),
    Column("current_job_id", Text),
    Column("current_job_type", Text),
    Column("current_run_id", Text),
    Column("current_session_id", Text),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("metadata", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("status in ('idle', 'running')", name="worker_heartbeats_status_check"),
)

skill_tags = Table(
    "skill_tags",
    metadata,
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("tag_group_id", Text, nullable=False),
    Column("tag_value", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    PrimaryKeyConstraint("skill_id", "tag_group_id", "tag_value"),
    ForeignKeyConstraint(
        ["tag_group_id", "tag_value"],
        ["tag_values.tag_group_id", "tag_values.value"],
        name="skill_tags_tag_value_fkey",
    ),
)

tag_groups = Table(
    "tag_groups",
    metadata,
    Column("id", Text, primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=text("''")),
    Column("sort_order", Integer, nullable=False, server_default=text("0")),
    Column("required", Boolean, nullable=False, server_default=text("false")),
    Column("free_form", Boolean, nullable=False, server_default=text("false")),
    timestamp_column(),
    timestamp_column("updated_at"),
    Column("created_by", Text, nullable=False),
    CheckConstraint("id ~ '^[A-Za-z0-9_-]+$'", name="tag_groups_id_format_check"),
    CheckConstraint("length(btrim(display_name)) > 0", name="tag_groups_display_name_non_empty"),
)

tag_values = Table(
    "tag_values",
    metadata,
    Column("tag_group_id", Text, ForeignKey("tag_groups.id"), nullable=False),
    Column("value", Text, nullable=False),
    Column("display_name", Text),
    Column("description", Text, nullable=False, server_default=text("''")),
    Column("sort_order", Integer, nullable=False, server_default=text("0")),
    timestamp_column(),
    timestamp_column("updated_at"),
    Column("created_by", Text, nullable=False),
    PrimaryKeyConstraint("tag_group_id", "value"),
    CheckConstraint("length(btrim(value)) > 0", name="tag_values_value_non_empty"),
)

tag_group_cascades = Table(
    "tag_group_cascades",
    metadata,
    Column("child_tag_group_id", Text, ForeignKey("tag_groups.id"), primary_key=True),
    Column("parent_tag_group_id", Text, nullable=False),
    Column("parent_tag_value", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    ForeignKeyConstraint(
        ["parent_tag_group_id", "parent_tag_value"],
        ["tag_values.tag_group_id", "tag_values.value"],
        name="tag_group_cascades_parent_value_fkey",
    ),
    CheckConstraint("child_tag_group_id <> parent_tag_group_id", name="tag_group_cascades_no_self_parent_check"),
)

groups = Table(
    "groups",
    metadata,
    Column("id", Text, primary_key=True),
    Column("scope_type", Text, nullable=False, server_default=text("'global'")),
    Column("scope_id", Text, nullable=False, server_default=text("'default'")),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=text("''")),
    timestamp_column(),
    timestamp_column("updated_at"),
    Column("created_by", Text, nullable=False),
    CheckConstraint("scope_type in ('global', 'skill')", name="groups_scope_type_check"),
    UniqueConstraint("scope_type", "scope_id", "name", name="groups_scope_name_unique"),
)

group_memberships = Table(
    "group_memberships",
    metadata,
    Column("group_id", Text, ForeignKey("groups.id"), nullable=False),
    Column("subject_type", Text, nullable=False),
    Column("subject_id", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    PrimaryKeyConstraint("group_id", "subject_type", "subject_id"),
    CheckConstraint("subject_type in ('user')", name="group_memberships_subject_type_check"),
)

role_assignments = Table(
    "role_assignments",
    metadata,
    Column("id", Text, primary_key=True),
    Column("subject_type", Text, nullable=False),
    Column("subject_id", Text, nullable=False),
    Column("resource_type", Text, nullable=False),
    Column("resource_id", Text, nullable=False),
    Column("role", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("subject_type in ('user', 'group')", name="role_assignments_subject_type_check"),
    CheckConstraint("resource_type in ('skill', 'skill_tag')", name="role_assignments_resource_type_check"),
    CheckConstraint("role in ('admin', 'owner', 'maintainer', 'evaluator', 'reviewer', 'viewer')", name="role_assignments_role_check"),
    UniqueConstraint("subject_type", "subject_id", "resource_type", "resource_id", "role", name="role_assignments_scope_unique"),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("id", Text, primary_key=True),
    Column("actor_ref", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("resource_type", Text, nullable=False),
    Column("resource_id", Text, nullable=False),
    Column("payload", JSONB(), nullable=False, server_default=text("'{}'::jsonb")),
    timestamp_column(),
)

from skillhub.models.schema import indexes as _indexes  # noqa: E402,F401
