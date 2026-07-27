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


def test_skill_identity_revision_upgrades_the_baseline_without_data_loss() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        upgrade_database(engine, "0001_initial_schema")
        with engine.begin() as connection:
            connection.execute(
                text("insert into skills (id, slug, owner_ref) values ('skill-existing', 'existing-skill', 'owner')")
            )

        upgrade_database(engine)

        assert current_revision(engine) == "0003_workflow_skill_generators"
        with engine.connect() as connection:
            assert "display_name" in {column["name"] for column in inspect(connection).get_columns("skills")}
            assert connection.scalar(text("select slug from skills where id = 'skill-existing'")) == "existing-skill"
            constraints = {item["name"] for item in inspect(connection).get_check_constraints("role_assignments")}
            assert "role_assignments_global_admin_check" in constraints
    finally:
        _reset_database(engine)
        engine.dispose()


def test_workflow_generator_revision_backfills_existing_sync_evidence() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        upgrade_database(engine, "0002_skill_identity_global_admin")
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    insert into skills (id, slug, owner_ref)
                    values ('skill-workflow', 'workflow-skill', 'owner')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    insert into artifacts (
                        id, kind, namespace, locator, digest, media_type,
                        size_bytes, content_text, created_by
                    ) values (
                        'artifact-source', 'workflow_source', 'migration-test',
                        'inline:source', 'source-digest', 'text/plain', 2, '{}', 'owner'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    insert into skill_versions (
                        id, skill_id, version_number, version, content_ref,
                        content_digest, change_summary, created_by
                    ) values (
                        'skillver-workflow', 'skill-workflow', 1, '1.0.0',
                        '{"kind":"artifact","locator":"artifact:artifact-source","digest":"legacy-content-digest"}'::jsonb,
                        'legacy-content-digest', 'legacy sync', 'owner'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    update skills
                    set current_version_id = 'skillver-workflow'
                    where id = 'skill-workflow'
                    """
                )
            )
            connection.execute(
                text(
                    """
                    insert into workflows (
                        id, skill_id, revision, document_schema_version, document,
                        document_digest, created_by, last_saved_by
                    ) values (
                        'workflow-existing', 'skill-workflow', 2, 3, '{}'::jsonb,
                        'document-digest', 'owner', 'owner'
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    insert into workflow_syncs (
                        id, workflow_id, workflow_revision, document_schema_version,
                        source_artifact_id, skill_version_id, generator_version, created_by
                    ) values (
                        'sync-existing', 'workflow-existing', 2, 3,
                        'artifact-source', 'skillver-workflow', 'workflow-skill-v3', 'owner'
                    )
                    """
                )
            )

        upgrade_database(engine)

        assert current_revision(engine) == "0003_workflow_skill_generators"
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    select generator_id, generator_version, generator_options,
                           generator_options_digest, preview_digest
                    from workflow_syncs
                    where id = 'sync-existing'
                    """
                )
            ).mappings().one()
            assert dict(row) == {
                "generator_id": "builtin.single-file",
                "generator_version": "workflow-skill-v3",
                "generator_options": {},
                "generator_options_digest": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
                "preview_digest": "legacy-content-digest",
            }
            unique_names = {
                item["name"]
                for item in inspect(connection).get_unique_constraints("workflow_syncs")
            }
            assert unique_names == {
                "workflow_syncs_generator_identity_unique",
                "workflow_syncs_skill_version_unique",
            }
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
