"""Merge Workflow log SQL and single-step debug revisions.

Revision ID: 0006_workflow_log_debug_merge
Revises: 0005_workflow_log_sql_v5, 0005_workflow_step_debug
"""

from __future__ import annotations

revision = "0006_workflow_log_debug_merge"
down_revision = ("0005_workflow_log_sql_v5", "0005_workflow_step_debug")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
