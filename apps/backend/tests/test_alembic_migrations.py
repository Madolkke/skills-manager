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
            connection.execute(text("insert into skills (id, slug, owner_ref) values ('skill-existing', 'existing-skill', 'owner')"))

        upgrade_database(engine)

        assert current_revision(engine) == "0003_workflow_json_schema_v4"
        with engine.connect() as connection:
            assert "display_name" in {column["name"] for column in inspect(connection).get_columns("skills")}
            assert connection.scalar(text("select slug from skills where id = 'skill-existing'")) == "existing-skill"
            constraints = {item["name"] for item in inspect(connection).get_check_constraints("role_assignments")}
            assert "role_assignments_global_admin_check" in constraints
    finally:
        _reset_database(engine)
        engine.dispose()


def test_workflow_json_schema_revision_preserves_v3_collection_history() -> None:
    ensure_postgres_test_database()
    engine = create_postgres_engine(resolve_database_url())
    try:
        _reset_database(engine)
        upgrade_database(engine, "0002_skill_identity_global_admin")
        workflow_document = {
            "documentType": "workflow_bundle",
            "workflow": {
                "id": "workflow-v3",
                "revision": 1,
                "metadata": {"name": "迁移", "description": "迁移测试"},
                "inputs": [{"id": "input-rows", "key": "rows", "name": "数据行", "description": "", "dataType": "array", "required": True}],
                "deviceRoles": [],
                "nodes": [],
            },
            "collectionSnapshots": [],
        }
        collection_document = {
            "id": "collection-v3",
            "revision": 1,
            "key": "legacy",
            "metadata": {"name": "旧采集", "description": "", "industry": "", "device": "", "versions": [], "tags": []},
            "spec": {"collectionType": "cli", "commandTemplate": "show legacy", "outputSamples": []},
            "inputs": [],
            "outputs": [{"id": "output-table", "key": "table", "description": "旧对象", "dataType": "object"}],
        }
        with engine.begin() as connection:
            connection.execute(metadata.tables["skills"].insert().values(id="skill-v3", slug="workflow-v3", owner_ref="owner"))
            connection.execute(
                metadata.tables["workflows"]
                .insert()
                .values(
                    id="workflow-v3",
                    skill_id="skill-v3",
                    revision=1,
                    document_schema_version=3,
                    document=workflow_document,
                    document_digest="old",
                    created_by="tester",
                    last_saved_by="tester",
                )
            )
            connection.execute(metadata.tables["workflow_collection_definitions"].insert().values(id="collection-v3", latest_revision=1, created_by="tester"))
            connection.execute(
                metadata.tables["workflow_collection_revisions"]
                .insert()
                .values(
                    definition_id="collection-v3",
                    revision=1,
                    document_schema_version=3,
                    definition=collection_document,
                    definition_digest="old",
                    created_by="tester",
                )
            )

        upgrade_database(engine)

        with engine.connect() as connection:
            workflow = connection.execute(text("select revision, document_schema_version, document from workflows where id='workflow-v3'")).mappings().one()
            revisions = (
                connection.execute(
                    text(
                        "select revision, document_schema_version, definition from workflow_collection_revisions where definition_id='collection-v3' order by revision"
                    )
                )
                .mappings()
                .all()
            )
            assert workflow["revision"] == 2
            assert workflow["document_schema_version"] == 4
            assert workflow["document"]["workflow"]["inputs"][0]["schema"]["items"]["x-skillhub-legacy-loose"] is True
            assert [(item["revision"], item["document_schema_version"]) for item in revisions] == [(1, 3), (2, 4)]
            assert revisions[0]["definition"]["outputs"][0]["dataType"] == "object"
            assert revisions[1]["definition"]["outputs"][0]["schema"]["additionalProperties"] is True
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
