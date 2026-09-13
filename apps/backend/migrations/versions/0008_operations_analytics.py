"""增加运营统计事实并回填现存 Skill 的首次创建记录。"""

import sqlalchemy as sa
from alembic import op

revision = "0008_operations_analytics"
down_revision = "0007_command_library"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建独立统计表；不根据审计或接口日志伪造历史访问。"""
    op.create_table(
        "skill_creation_facts",
        sa.Column("skill_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_ref", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("skill_creation_facts_created_idx", "skill_creation_facts", ["created_at"])
    op.create_table(
        "skill_visit_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("skill_visit_events_time_idx", "skill_visit_events", ["visited_at"])
    op.create_index("skill_visit_events_skill_time_idx", "skill_visit_events", ["skill_id", "visited_at"])
    op.create_table(
        "analytics_collection_state",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("visits_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creation_history_note", sa.Text(), nullable=False),
        sa.Column("demo_started_at", sa.DateTime(timezone=True)),
    )
    op.execute("INSERT INTO skill_creation_facts (skill_id, name, owner_ref, created_at) "
               "SELECT id, coalesce(display_name, slug), owner_ref, created_at FROM skills")
    op.execute(sa.text("INSERT INTO analytics_collection_state (id, visits_started_at, creation_history_note) "
                       "VALUES ('default', now(), '历史新增仅回填上线时仍存在的 Skill；此前永久删除的 Skill 无法恢复。')"))


def downgrade() -> None:
    """移除本次迁移创建的统计表。"""
    op.drop_table("skill_visit_events")
    op.drop_table("skill_creation_facts")
    op.drop_table("analytics_collection_state")
