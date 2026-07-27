"""Add versioned Workflow Skill Generator evidence.

Revision ID: 0003_workflow_skill_generators
Revises: 0002_skill_identity_global_admin
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_workflow_skill_generators"
down_revision = "0002_skill_identity_global_admin"
branch_labels = None
depends_on = None

EMPTY_OPTIONS_DIGEST = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def upgrade() -> None:
    op.add_column("workflow_syncs", sa.Column("generator_id", sa.Text(), nullable=True))
    op.add_column(
        "workflow_syncs",
        sa.Column(
            "generator_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("workflow_syncs", sa.Column("generator_options_digest", sa.Text(), nullable=True))
    op.add_column("workflow_syncs", sa.Column("preview_digest", sa.Text(), nullable=True))

    op.execute("update workflow_syncs set generator_id = 'builtin.single-file'")
    op.execute(
        sa.text("update workflow_syncs set generator_options_digest = :digest").bindparams(
            digest=EMPTY_OPTIONS_DIGEST
        )
    )
    op.execute(
        """
        update workflow_syncs as sync
        set preview_digest = version.content_digest
        from skill_versions as version
        where version.id = sync.skill_version_id
        """
    )

    op.alter_column("workflow_syncs", "generator_id", nullable=False)
    op.alter_column("workflow_syncs", "generator_options_digest", nullable=False)
    op.alter_column("workflow_syncs", "preview_digest", nullable=False)
    op.drop_constraint("workflow_syncs_workflow_revision_unique", "workflow_syncs", type_="unique")
    op.create_unique_constraint(
        "workflow_syncs_generator_identity_unique",
        "workflow_syncs",
        [
            "workflow_id",
            "workflow_revision",
            "generator_id",
            "generator_version",
            "generator_options_digest",
        ],
    )


def downgrade() -> None:
    op.drop_constraint("workflow_syncs_generator_identity_unique", "workflow_syncs", type_="unique")
    op.execute(
        """
        delete from workflow_syncs
        where id in (
            select id
            from (
                select
                    id,
                    row_number() over (
                        partition by workflow_id, workflow_revision
                        order by created_at desc, id desc
                    ) as position
                from workflow_syncs
            ) as ranked
            where position > 1
        )
        """
    )
    op.create_unique_constraint(
        "workflow_syncs_workflow_revision_unique",
        "workflow_syncs",
        ["workflow_id", "workflow_revision"],
    )
    op.drop_column("workflow_syncs", "preview_digest")
    op.drop_column("workflow_syncs", "generator_options_digest")
    op.drop_column("workflow_syncs", "generator_options")
    op.drop_column("workflow_syncs", "generator_id")
