"""Add Skill display names and global Skill administrators.

Revision ID: 0002_skill_identity_global_admin
Revises: 0001_initial_schema
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_skill_identity_global_admin"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("skills", sa.Column("display_name", sa.Text(), nullable=True))
    op.create_check_constraint(
        "skills_display_name_length_check",
        "skills",
        "display_name is null or length(btrim(display_name)) between 1 and 120",
    )

    op.drop_constraint("role_assignments_resource_type_check", "role_assignments", type_="check")
    op.create_check_constraint(
        "role_assignments_resource_type_check",
        "role_assignments",
        "resource_type in ('skill', 'skill_tag', 'global')",
    )
    op.create_check_constraint(
        "role_assignments_global_admin_check",
        "role_assignments",
        "resource_type <> 'global' or (resource_id = 'skills' and subject_type = 'user' and role = 'admin')",
    )


def downgrade() -> None:
    op.execute("delete from role_assignments where resource_type = 'global'")
    op.drop_constraint("role_assignments_global_admin_check", "role_assignments", type_="check")
    op.drop_constraint("role_assignments_resource_type_check", "role_assignments", type_="check")
    op.create_check_constraint(
        "role_assignments_resource_type_check",
        "role_assignments",
        "resource_type in ('skill', 'skill_tag')",
    )

    op.drop_constraint("skills_display_name_length_check", "skills", type_="check")
    op.drop_column("skills", "display_name")
