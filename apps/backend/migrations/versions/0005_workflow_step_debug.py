"""Add Workflow single-step debug cases and runs.

Revision ID: 0005_workflow_step_debug
Revises: 0004_workflow_json_schema_v4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_workflow_step_debug"
down_revision = "0004_workflow_json_schema_v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_debug_cases",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("expected_target_id", sa.Text(), nullable=False),
        sa.Column("workflow_inputs", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("collection_fixtures", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("length(btrim(name)) > 0", name="workflow_debug_cases_name_length_check"),
        sa.CheckConstraint("jsonb_typeof(workflow_inputs) = 'object'", name="workflow_debug_cases_inputs_object"),
        sa.CheckConstraint("jsonb_typeof(collection_fixtures) = 'object'", name="workflow_debug_cases_fixtures_object"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("workflow_debug_cases_skill_step_idx", "workflow_debug_cases", ["skill_id", "step_id"])

    op.create_table(
        "workflow_debug_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("case_id", sa.Text(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        sa.Column("expected_target_id", sa.Text(), nullable=False),
        sa.Column("case_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("workflow_revision", sa.Integer(), nullable=False),
        sa.Column("workflow_digest", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("executor_run_id", sa.Text(), nullable=True),
        sa.Column("executor_identity", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("executor_status", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resumed_pauses", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("workflow_revision > 0", name="workflow_debug_runs_revision_positive"),
        sa.CheckConstraint(
            "status in ('starting', 'running', 'paused', 'completed', 'failed', 'external_state_unknown')",
            name="workflow_debug_runs_status_check",
        ),
        sa.CheckConstraint("jsonb_typeof(case_snapshot) = 'object'", name="workflow_debug_runs_snapshot_object"),
        sa.CheckConstraint("jsonb_typeof(executor_identity) = 'object'", name="workflow_debug_runs_identity_object"),
        sa.CheckConstraint("jsonb_typeof(resumed_pauses) = 'array'", name="workflow_debug_runs_pauses_array"),
        sa.ForeignKeyConstraint(["case_id"], ["workflow_debug_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("executor_run_id", name="workflow_debug_runs_executor_run_id_unique"),
        sa.UniqueConstraint("task_id", name="workflow_debug_runs_task_id_unique"),
    )
    op.create_index(
        "workflow_debug_runs_case_created_idx",
        "workflow_debug_runs",
        ["case_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "workflow_debug_runs_case_active_unique",
        "workflow_debug_runs",
        ["case_id"],
        unique=True,
        postgresql_where=sa.text("status in ('starting', 'running', 'paused', 'external_state_unknown')"),
    )


def downgrade() -> None:
    op.drop_index("workflow_debug_runs_case_active_unique", table_name="workflow_debug_runs")
    op.drop_index("workflow_debug_runs_case_created_idx", table_name="workflow_debug_runs")
    op.drop_table("workflow_debug_runs")
    op.drop_index("workflow_debug_cases_skill_step_idx", table_name="workflow_debug_cases")
    op.drop_table("workflow_debug_cases")
