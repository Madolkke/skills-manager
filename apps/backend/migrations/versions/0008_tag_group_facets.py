"""Add Tag Group display modes and parent-selected cascades.

Revision ID: 0008_tag_group_facets
Revises: 0007_command_library
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0008_tag_group_facets"
down_revision = "0007_command_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tag_groups",
        sa.Column("display_mode", sa.Text(), nullable=False, server_default=sa.text("'checkbox'")),
    )
    op.create_check_constraint(
        "tag_groups_display_mode_check",
        "tag_groups",
        "display_mode in ('checkbox', 'multi_select')",
    )

    op.drop_constraint("tag_group_cascades_parent_value_fkey", "tag_group_cascades", type_="foreignkey")
    op.alter_column("tag_group_cascades", "parent_tag_value", existing_type=sa.Text(), nullable=True)
    op.add_column(
        "tag_group_cascades",
        sa.Column("activation_mode", sa.Text(), nullable=False, server_default=sa.text("'parent_value'")),
    )
    op.create_check_constraint(
        "tag_group_cascades_activation_mode_check",
        "tag_group_cascades",
        "activation_mode in ('parent_value', 'parent_selected')",
    )
    op.create_check_constraint(
        "tag_group_cascades_activation_value_check",
        "tag_group_cascades",
        "(activation_mode = 'parent_value' AND parent_tag_value IS NOT NULL) OR "
        "(activation_mode = 'parent_selected' AND parent_tag_value IS NULL)",
    )
    op.create_foreign_key(
        "tag_group_cascades_parent_value_fkey",
        "tag_group_cascades",
        "tag_values",
        ["parent_tag_group_id", "parent_tag_value"],
        ["tag_group_id", "value"],
    )
    op.create_foreign_key(
        "tag_group_cascades_parent_group_fkey",
        "tag_group_cascades",
        "tag_groups",
        ["parent_tag_group_id"],
        ["id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    parent_selected_count = bind.execute(
        sa.text(
            "SELECT count(*) FROM tag_group_cascades "
            "WHERE activation_mode = 'parent_selected'"
        )
    ).scalar_one()
    if parent_selected_count:
        raise RuntimeError(
            "Cannot downgrade 0008_tag_group_facets while parent_selected "
            "tag cascades exist. Delete or convert them first."
        )

    op.drop_constraint("tag_group_cascades_parent_group_fkey", "tag_group_cascades", type_="foreignkey")
    op.drop_constraint("tag_group_cascades_parent_value_fkey", "tag_group_cascades", type_="foreignkey")
    op.drop_constraint("tag_group_cascades_activation_value_check", "tag_group_cascades", type_="check")
    op.drop_constraint("tag_group_cascades_activation_mode_check", "tag_group_cascades", type_="check")
    op.drop_column("tag_group_cascades", "activation_mode")
    op.alter_column("tag_group_cascades", "parent_tag_value", existing_type=sa.Text(), nullable=False)
    op.create_foreign_key(
        "tag_group_cascades_parent_value_fkey",
        "tag_group_cascades",
        "tag_values",
        ["parent_tag_group_id", "parent_tag_value"],
        ["tag_group_id", "value"],
    )
    op.drop_constraint("tag_groups_display_mode_check", "tag_groups", type_="check")
    op.drop_column("tag_groups", "display_mode")
