import json
from importlib import import_module

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from skillhub.models.entities import digest_text
from skillhub.models.schema import metadata
from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.migrations import alembic_config, current_revision, expected_revision, prepare_database, upgrade_database
from skillhub.models.store import SkillHubStore
from tests.conftest import ensure_postgres_test_database
from tests.workflow_migration_fixture import COLLECTION_DOCUMENTS, seed_v3_workflow_state

EMPTY_OPTIONS_DIGEST = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


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
            connection.execute(text("insert into skills (id, slug, owner_ref) values ('skill-existing', 'existing-skill', 'owner')"))

        upgrade_database(engine)

        assert current_revision(engine) == expected_revision()
        with engine.connect() as connection:
            assert "display_name" in {column["name"] for column in inspect(connection).get_columns("skills")}
            assert connection.scalar(text("select slug from skills where id = 'skill-existing'")) == "existing-skill"
            constraints = {item["name"] for item in inspect(connection).get_check_constraints("role_assignments")}
            assert "role_assignments_global_admin_check" in constraints
    finally:
        _reset_database(engine)
        engine.dispose()


def test_workflow_migrations_preserve_history_and_mark_existing_sync_changed() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        upgrade_database(engine, "0002_skill_identity_global_admin")
        with engine.begin() as connection:
            seed_v3_workflow_state(connection)

        upgrade_database(engine, "0003_workflow_skill_generators")

        assert current_revision(engine) == "0003_workflow_skill_generators"
        with engine.connect() as connection:
            evidence = connection.execute(
                text(
                    """
                    select generator_id, generator_version, generator_options,
                           generator_options_digest, preview_digest
                    from workflow_syncs where id = 'sync-existing'
                    """
                )
            ).mappings().one()
            assert dict(evidence) == {
                "generator_id": "builtin.single-file",
                "generator_version": "workflow-skill-v3",
                "generator_options": {},
                "generator_options_digest": EMPTY_OPTIONS_DIGEST,
                "preview_digest": "legacy-content-digest",
            }
            unique_names = {item["name"] for item in inspect(connection).get_unique_constraints("workflow_syncs")}
            assert unique_names == {
                "workflow_syncs_generator_identity_unique",
                "workflow_syncs_skill_version_unique",
            }

        upgrade_database(engine)

        assert current_revision(engine) == expected_revision()
        with engine.connect() as connection:
            workflow = connection.execute(
                text(
                    """
                    select revision, document_schema_version, document,
                           document_digest, last_saved_by
                    from workflows where id = 'workflow-v3'
                    """
                )
            ).mappings().one()
            revisions = connection.execute(
                text(
                    """
                    select revision, document_schema_version, definition,
                           definition_digest
                    from workflow_collection_revisions
                    where definition_id = 'collection-v3'
                    order by revision
                    """
                )
            ).mappings().all()
            sync = connection.execute(
                text(
                    """
                    select workflow_revision, document_schema_version,
                           source_artifact_id, skill_version_id, generator_id,
                           generator_version, generator_options,
                           generator_options_digest, preview_digest
                    from workflow_syncs where id = 'sync-existing'
                    """
                )
            ).mappings().one()

            assert workflow["revision"] == 2
            assert workflow["document_schema_version"] == 4
            assert workflow["last_saved_by"] == "system:migration:workflow-json-schema-v4"
            assert workflow["document_digest"] == _canonical_digest(workflow["document"])
            assert workflow["document"]["workflow"]["inputs"][0]["schema"]["items"]["x-skillhub-legacy-loose"] is True
            reference = workflow["document"]["workflow"]["nodes"][0]["collectionCalls"][0]["definition"]
            assert reference == {"id": "collection-v3", "revision": 3}
            assert [(row["revision"], row["document_schema_version"]) for row in revisions] == [
                (1, 3),
                (2, 3),
                (3, 4),
                (4, 4),
            ]
            assert revisions[0]["definition"] == COLLECTION_DOCUMENTS[0]
            assert revisions[1]["definition"] == COLLECTION_DOCUMENTS[1]
            assert revisions[2]["definition"]["outputs"][0]["schema"]["additionalProperties"] is True
            assert revisions[2]["definition_digest"] == _canonical_digest(revisions[2]["definition"])
            assert workflow["document"]["collectionSnapshots"] == [revisions[2]["definition"]]
            assert connection.scalar(text("select latest_revision from workflow_collection_definitions where id='collection-v3'")) == 4
            user_command = connection.execute(
                text(
                    """
                    select workflow_id, collection_id, expression, normalized_expression, document
                    from user_command_library_entries
                    where workflow_id = 'workflow-v3' and collection_id = 'collection-v3'
                    """
                )
            ).mappings().one()
            assert dict(user_command) == {
                "workflow_id": "workflow-v3",
                "collection_id": "collection-v3",
                "expression": "show legacy 1",
                "normalized_expression": "show legacy 1",
                "document": {
                    "metadata": revisions[2]["definition"]["metadata"],
                    "samples": [],
                    "outputSchema": {
                        "type": "object",
                        "properties": {"table": revisions[2]["definition"]["outputs"][0]["schema"]},
                        "required": ["table"],
                        "additionalProperties": False,
                    },
                    "ttp": "",
                },
            }
            assert dict(sync) == {
                "workflow_revision": 1,
                "document_schema_version": 3,
                "source_artifact_id": "artifact-source",
                "skill_version_id": "skillver-workflow",
                "generator_id": "builtin.single-file",
                "generator_version": "workflow-skill-v3",
                "generator_options": {},
                "generator_options_digest": EMPTY_OPTIONS_DIGEST,
                "preview_digest": "legacy-content-digest",
            }
            assert connection.scalar(text("select content_text from artifacts where id='artifact-source'")) == "{}"
            assert connection.scalar(text("select content_digest from skill_versions where id='skillver-workflow'")) == "legacy-content-digest"
        assert SkillHubStore(engine).workflow_detail(skill_id="skill-v3", actor="owner")["sync"]["status"] == "workflow_changed"
    finally:
        _reset_database(engine)
        engine.dispose()


def test_workflow_document_schema_revisions_reject_downgrade() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        upgrade_database(engine)
        config = alembic_config()
        with pytest.raises(RuntimeError, match="irreversible"), engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0003_workflow_skill_generators")
        assert current_revision(engine) == expected_revision()
    finally:
        _reset_database(engine)
        engine.dispose()


def test_prepare_database_bridges_legacy_workflow_json_schema_revision() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        upgrade_database(engine, "0002_skill_identity_global_admin")
        with engine.begin() as connection:
            seed_v3_workflow_state(connection)
            migration = import_module("migrations.versions.0004_workflow_json_schema_v4")
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            connection.execute(
                text("update alembic_version set version_num = '0003_workflow_json_schema_v4'")
            )

        prepare_database(engine)

        assert current_revision(engine) == expected_revision()
        with engine.connect() as connection:
            workflow = connection.execute(
                text("select revision, document_schema_version from workflows where id = 'workflow-v3'")
            ).one()
            assert workflow == (2, 4)
            columns = {item["name"] for item in inspect(connection).get_columns("workflow_syncs")}
            assert {"generator_id", "generator_options", "generator_options_digest", "preview_digest"} <= columns
            assert {"workflow_debug_cases", "workflow_debug_runs"} <= set(inspect(connection).get_table_names())
    finally:
        _reset_database(engine)
        engine.dispose()


@pytest.mark.parametrize("branch_revision", ["0005_workflow_log_sql_v5", "0005_workflow_step_debug"])
def test_workflow_merge_revision_upgrades_either_branch_to_one_head(branch_revision: str) -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        upgrade_database(engine, branch_revision)

        upgrade_database(engine)

        assert current_revision(engine) == expected_revision()
        with engine.connect() as connection:
            assert {"workflow_debug_cases", "workflow_debug_runs"} <= set(inspect(connection).get_table_names())
            workflow_default = next(
                item["default"]
                for item in inspect(connection).get_columns("workflows")
                if item["name"] == "document_schema_version"
            )
            assert str(workflow_default).strip("'\"") == "5"
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


def _canonical_digest(value) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return digest_text(canonical)


def _reset_database(engine) -> None:
    metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("drop table if exists alembic_version"))
