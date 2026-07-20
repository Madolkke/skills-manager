import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from skillhub.models.schema import metadata
from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.migrations import current_revision, expected_revision, prepare_database, upgrade_database
from tests.conftest import ensure_postgres_test_database


def test_alembic_upgrade_builds_schema_without_metadata_drift() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("drop table if exists alembic_version"))
        upgrade_database(engine)

        assert current_revision(engine) == expected_revision()
        assert set(metadata.tables) <= set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), metadata) == []
            assert connection.execute(text("select target_key from publish_targets order by target_key")).scalars().all() == [
                "agentcenter",
                "custom1",
                "custom2",
                "yunxi",
            ]
    finally:
        metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("drop table if exists alembic_version"))
        engine.dispose()


def test_prepare_database_adopts_exact_unversioned_schema_without_data_loss() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("insert into groups (id, name, created_by) values ('existing', 'Existing', 'tester')"))

        prepare_database(engine)

        assert current_revision(engine) == expected_revision()
        with engine.connect() as connection:
            assert connection.scalar(text("select name from groups where id = 'existing'")) == "Existing"
            assert connection.scalar(text("select count(*) from publish_targets")) == 4
    finally:
        _reset_database(engine)
        engine.dispose()


def test_prepare_database_rejects_mismatched_unversioned_schema_without_cleanup() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("insert into groups (id, name, created_by) values ('existing', 'Existing', 'tester')"))
            connection.execute(text("alter table groups add column unexpected_column text"))

        with pytest.raises(RuntimeError, match="does not match"):
            prepare_database(engine)

        assert current_revision(engine) is None
        with engine.connect() as connection:
            assert connection.scalar(text("select name from groups where id = 'existing'")) == "Existing"
            assert "unexpected_column" in {column["name"] for column in inspect(connection).get_columns("groups")}
    finally:
        _reset_database(engine)
        engine.dispose()


def _reset_database(engine) -> None:
    metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("drop table if exists alembic_version"))
