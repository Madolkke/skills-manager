"""Seed fixed publish targets.

Revision ID: 0002_seed_publish_targets
Revises: 0001_orm_baseline
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_seed_publish_targets"
down_revision = "0001_orm_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    targets = sa.table(
        "publish_targets",
        sa.column("id", sa.Text()),
        sa.column("target_key", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("enabled", sa.Boolean()),
        sa.column("auto_publish_enabled", sa.Boolean()),
        sa.column("gate_expression", postgresql.JSONB()),
        sa.column("config", postgresql.JSONB()),
        sa.column("created_by", sa.Text()),
    )
    default_gate = {
        "type": "group",
        "op": "and",
        "children": [
            {"type": "check", "check_id": "min_responses", "params": {"min": 1}},
            {"type": "check", "check_id": "no_negative_score", "params": {}},
        ],
    }
    rows = [
        ("target_yunxi", "yunxi", "云析", "云析发布源"),
        ("target_agentcenter", "agentcenter", "AgentCenter", "AgentCenter 发布源"),
        ("target_custom1", "custom1", "自定义1", "预留自定义发布源 1"),
        ("target_custom2", "custom2", "自定义2", "预留自定义发布源 2"),
    ]
    statement = postgresql.insert(targets).values(
        [
            {
                "id": target_id,
                "target_key": key,
                "name": name,
                "description": description,
                "enabled": True,
                "auto_publish_enabled": False,
                "gate_expression": default_gate,
                "config": {},
                "created_by": "system",
            }
            for target_id, key, name, description in rows
        ]
    )
    op.execute(
        statement.on_conflict_do_update(
            index_elements=[targets.c.target_key],
            set_={
                "name": statement.excluded.name,
                "description": statement.excluded.description,
                "config": statement.excluded.config,
                "gate_expression": sa.case(
                    (targets.c.gate_expression == sa.cast({}, postgresql.JSONB()), statement.excluded.gate_expression),
                    else_=targets.c.gate_expression,
                ),
            },
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "delete from publish_targets "
            "where target_key in ('yunxi', 'agentcenter', 'custom1', 'custom2')"
        )
    )
