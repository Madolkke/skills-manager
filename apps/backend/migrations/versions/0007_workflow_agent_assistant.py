"""Add Workflow Agent assistant persistence.

Revision ID: 0007_workflow_agent_assistant
Revises: 0006_workflow_log_debug_merge
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_workflow_agent_assistant"
down_revision = "0006_workflow_log_debug_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS workflow_agent_scope")
    op.create_table(
        "workflow_agent_sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("actor_ref", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("agentscope_sessions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('active', 'archived')", name="workflow_agent_sessions_status_check"),
        sa.CheckConstraint("jsonb_typeof(agentscope_sessions) = 'object'", name="workflow_agent_sessions_scope_map_object"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("workflow_agent_sessions_actor_skill_active_unique", "workflow_agent_sessions", ["actor_ref", "skill_id"], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index("workflow_agent_sessions_skill_updated_idx", "workflow_agent_sessions", ["skill_id", sa.text("updated_at DESC")])
    op.create_table(
        "workflow_agent_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'starting'"), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("selection", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("base_workflow_digest", sa.Text(), nullable=False),
        sa.Column("draft_digest", sa.Text(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('starting', 'running', 'completed', 'failed', 'canceled', 'interrupted')", name="workflow_agent_runs_status_check"),
        sa.CheckConstraint("base_revision > 0", name="workflow_agent_runs_revision_positive"),
        sa.CheckConstraint("jsonb_typeof(selection) = 'object'", name="workflow_agent_runs_selection_object"),
        sa.CheckConstraint("jsonb_typeof(context_snapshot) = 'object'", name="workflow_agent_runs_context_object"),
        sa.CheckConstraint("jsonb_typeof(usage) = 'object'", name="workflow_agent_runs_usage_object"),
        sa.ForeignKeyConstraint(["session_id"], ["workflow_agent_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("workflow_agent_runs_session_active_unique", "workflow_agent_runs", ["session_id"], unique=True, postgresql_where=sa.text("status in ('starting', 'running')"))
    op.create_index("workflow_agent_runs_session_created_idx", "workflow_agent_runs", ["session_id", sa.text("created_at DESC")])
    _create_event_and_proposal_tables()


def _create_event_and_proposal_tables() -> None:
    op.create_table(
        "workflow_agent_events",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("native_event_id", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence > 0", name="workflow_agent_events_sequence_positive"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="workflow_agent_events_payload_object"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="workflow_agent_events_run_sequence_unique"),
    )
    op.create_index("workflow_agent_events_run_sequence_idx", "workflow_agent_events", ["run_id", "sequence"])
    op.create_table(
        "workflow_agent_proposals",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("base_workflow_digest", sa.Text(), nullable=False),
        sa.Column("draft_digest", sa.Text(), nullable=False),
        sa.Column("applied_result", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind in ('debug_case_draft')", name="workflow_agent_proposals_kind_check"),
        sa.CheckConstraint("status in ('proposed', 'applied', 'stale')", name="workflow_agent_proposals_status_check"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="workflow_agent_proposals_payload_object"),
        sa.CheckConstraint("jsonb_typeof(applied_result) = 'object'", name="workflow_agent_proposals_result_object"),
        sa.ForeignKeyConstraint(["run_id"], ["workflow_agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="workflow_agent_proposals_run_unique"),
    )
    op.create_index("workflow_agent_proposals_skill_status_idx", "workflow_agent_proposals", ["skill_id", "status"])


def downgrade() -> None:
    op.drop_table("workflow_agent_proposals")
    op.drop_table("workflow_agent_events")
    op.drop_table("workflow_agent_runs")
    op.drop_table("workflow_agent_sessions")
    op.execute("DROP SCHEMA IF EXISTS workflow_agent_scope CASCADE")
