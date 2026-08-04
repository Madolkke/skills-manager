"""Add the Workflow v5 log SQL document contract defaults.

Revision ID: 0005_workflow_log_sql_v5
Revises: 0004_workflow_json_schema_v4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_workflow_log_sql_v5"
down_revision = "0004_workflow_json_schema_v4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("workflows", "document_schema_version", server_default=sa.text("5"), existing_type=sa.Integer(), nullable=False)
    op.alter_column("workflow_collection_revisions", "document_schema_version", server_default=sa.text("5"), existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    raise RuntimeError("Workflow log SQL v5 migration is irreversible.")
