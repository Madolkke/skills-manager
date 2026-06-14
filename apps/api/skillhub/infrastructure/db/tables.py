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
# PostgreSQL migrations still execute schema.sql as the authoritative DDL.


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
    Column("slug", Text, nullable=False, unique=True),
    Column("owner_ref", Text, nullable=False),
    Column("current_version_id", Text),
    Column("lifecycle_status", Text, nullable=False, server_default=text("'active'")),
    timestamp_column(),
    timestamp_column("updated_at"),
    CheckConstraint("lifecycle_status in ('active', 'archived')", name="skills_lifecycle_status_check"),
)

skill_versions = Table(
    "skill_versions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("display_name", Text),
    Column("content_ref", JSONB(), nullable=False),
    Column("content_digest", Text, nullable=False),
    Column("change_summary", Text, nullable=False),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
    CheckConstraint("version_number > 0", name="skill_versions_version_number_positive"),
    UniqueConstraint("skill_id", "version_number", name="skill_versions_skill_version_unique"),
    UniqueConstraint("id", "skill_id", name="skill_versions_id_skill_unique"),
)

skills.append_constraint(
    ForeignKeyConstraint(["current_version_id", "id"], ["skill_versions.id", "skill_versions.skill_id"], name="skills_current_version_fkey")
)

eval_sets = Table(
    "eval_sets",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=text("''")),
    Column("lifecycle_status", Text, nullable=False, server_default=text("'active'")),
    timestamp_column(),
    timestamp_column("updated_at"),
    CheckConstraint("lifecycle_status in ('active', 'archived')", name="eval_sets_lifecycle_status_check"),
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
    Column("lifecycle_status", Text, nullable=False, server_default=text("'active'")),
    timestamp_column(),
    timestamp_column("updated_at"),
    CheckConstraint("lifecycle_status in ('active', 'archived')", name="eval_cases_lifecycle_status_check"),
    UniqueConstraint("id", "skill_id", name="eval_cases_id_skill_unique"),
)

eval_case_versions = Table(
    "eval_case_versions",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, nullable=False),
    Column("case_id", Text, nullable=False),
    Column("version_number", Integer, nullable=False),
    Column("input_artifact_id", Text, ForeignKey("artifacts.id"), nullable=False),
    Column("expected_output_artifact_id", Text, ForeignKey("artifacts.id"), nullable=False),
    Column("notes", Text),
    timestamp_column(),
    Column("created_by", Text, nullable=False),
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
    Column("case_version_id", Text, nullable=False),
    Column("position", Integer, nullable=False),
    PrimaryKeyConstraint("eval_set_id", "position"),
    CheckConstraint("position >= 0", name="eval_set_cases_position_non_negative"),
    UniqueConstraint("eval_set_id", "case_version_id", name="eval_set_cases_case_unique"),
    ForeignKeyConstraint(["eval_set_id", "skill_id"], ["eval_sets.id", "eval_sets.skill_id"], name="eval_set_cases_set_skill_fkey"),
    ForeignKeyConstraint(["case_version_id", "skill_id"], ["eval_case_versions.id", "eval_case_versions.skill_id"], name="eval_set_cases_case_skill_fkey"),
)

eval_runs = Table(
    "eval_runs",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, nullable=False),
    Column("skill_version_id", Text, nullable=False),
    Column("eval_set_id", Text, nullable=False),
    Column("strategy", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("environment_tags", ARRAY(Text), nullable=False, server_default=text("'{}'")),
    Column("run_context", JSONB(), nullable=False, server_default=text("'{}'")),
    Column("run_context_hash", Text, nullable=False),
    Column("summary", JSONB(), nullable=False, server_default=text("'{}'")),
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

saved_views = Table(
    "saved_views",
    metadata,
    Column("id", Text, primary_key=True),
    Column("skill_id", Text, ForeignKey("skills.id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("view_type", Text, nullable=False),
    Column("config", JSONB(), nullable=False, server_default=text("'{}'")),
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
    timestamp_column(),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("created_by", Text, nullable=False),
    Column("error", Text),
    CheckConstraint("status in ('queued', 'running', 'succeeded', 'failed', 'canceled')", name="jobs_status_check"),
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
    CheckConstraint("role in ('owner', 'maintainer', 'evaluator', 'viewer')", name="role_assignments_role_check"),
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
    Column("payload", JSONB(), nullable=False, server_default=text("'{}'")),
    timestamp_column(),
)

from skillhub.infrastructure.db import indexes as _indexes  # noqa: E402,F401
