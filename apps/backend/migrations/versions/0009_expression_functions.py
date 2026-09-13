"""Add the global expression function catalog."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_expression_functions"
down_revision = "0008_tag_group_facets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expression_functions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("parameter_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("return_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False, server_default=sa.text("'python'")),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="expression_functions_name_unique"),
        sa.CheckConstraint("length(trim(name)) > 0", name="expression_functions_name_nonempty"),
        sa.CheckConstraint("length(trim(body)) > 0", name="expression_functions_body_nonempty"),
        sa.CheckConstraint("length(trim(language)) > 0", name="expression_functions_language_nonempty"),
        sa.CheckConstraint("jsonb_typeof(parameter_schema) = 'object'", name="expression_functions_parameter_schema_object"),
        sa.CheckConstraint("jsonb_typeof(return_schema) = 'object'", name="expression_functions_return_schema_object"),
    )


def downgrade() -> None:
    op.drop_table("expression_functions")
