import runpy
import sys
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import insert, select, text

from skillhub.models.schema import metadata, orm
from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.migrations import current_revision, upgrade_database
from tests.conftest import ensure_postgres_test_database


@pytest.mark.parametrize("revision", ["0008_operations_analytics", "0009_expression_functions"])
def test_merge_upgrade_preserves_both_branch_data(revision, monkeypatch):
    """从任一已发布末端升级，显式 seed 不覆盖管理员修改。"""
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("drop table if exists alembic_version"))
        upgrade_database(engine, revision)
        with engine.begin() as connection:
            connection.execute(insert(orm.Skill).values(id="merge-existing", slug="merge-existing", owner_ref="owner"))
        upgrade_database(engine)
        assert current_revision(engine) == "0010_expression_analytics_merge"
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), metadata) == []
            assert connection.scalar(select(orm.Skill.slug)) == "merge-existing"
        script = Path(__file__).parents[1] / "scripts" / "seed_expression_functions.py"
        monkeypatch.setattr(sys, "argv", [str(script)])
        runpy.run_path(str(script), run_name="__main__")
        with engine.begin() as connection:
            connection.execute(text("update expression_functions set description='管理员修改', enabled=false where name='len'"))
        runpy.run_path(str(script), run_name="__main__")
        with engine.connect() as connection:
            assert connection.scalar(text("select count(*) from expression_functions")) == 14
            assert connection.execute(text("select description, enabled from expression_functions where name='len'")).one() == ("管理员修改", False)
    finally:
        metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("drop table if exists alembic_version"))
        engine.dispose()
