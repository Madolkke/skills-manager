"""合并运营统计与表达式函数库迁移历史。"""

revision = "0010_expression_analytics_merge"
down_revision = ("0008_operations_analytics", "0009_expression_functions")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """两条分支结构互不冲突，仅统一迁移末端。"""
    pass


def downgrade() -> None:
    """恢复两个末端，不删除业务数据。"""
    pass
