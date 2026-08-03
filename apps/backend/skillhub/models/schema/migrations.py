from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from skillhub.models.schema import metadata
from skillhub.models.schema.reference_data import seed_reference_data

BACKEND_ROOT = Path(__file__).resolve().parents[3]
LEGACY_WORKFLOW_JSON_SCHEMA_REVISION = "0003_workflow_json_schema_v4"
PRE_GENERATOR_REVISION = "0002_skill_identity_global_admin"
GENERATOR_REVISION = "0003_workflow_skill_generators"
CURRENT_WORKFLOW_JSON_SCHEMA_REVISION = "0004_workflow_json_schema_v4"


def alembic_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def expected_revision() -> str:
    revision = ScriptDirectory.from_config(alembic_config()).get_current_head()
    if revision is None:
        raise RuntimeError("Alembic has no head revision.")
    return revision


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def verify_database_revision(engine: Engine) -> None:
    current = current_revision(engine)
    expected = expected_revision()
    if current != expected:
        raise RuntimeError(
            f"Database schema revision is {current or 'unversioned'}, expected {expected}. "
            "Run `uv run alembic upgrade head` before starting SkillHub."
        )


def stamp_database(engine: Engine, revision: str = "head") -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.stamp(config, revision)


def upgrade_database(engine: Engine, revision: str = "head") -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def prepare_database(engine: Engine) -> None:
    """Adopt an exact existing schema or upgrade a versioned/fresh database."""
    revision = current_revision(engine)
    if revision == LEGACY_WORKFLOW_JSON_SCHEMA_REVISION:
        _adopt_legacy_workflow_json_schema_revision(engine)
    elif revision is None:
        application_tables = set(metadata.tables)
        existing_tables = set(inspect(engine).get_table_names())
        if application_tables & existing_tables:
            with engine.connect() as connection:
                differences = compare_metadata(MigrationContext.configure(connection), metadata)
            if differences:
                raise RuntimeError(
                    "Existing unversioned database does not match the ORM metadata. "
                    "No destructive automatic cleanup was attempted; migrate it explicitly before stamping Alembic."
                )
            with Session(engine) as session, session.begin():
                seed_reference_data(session)
            stamp_database(engine, "head")
    upgrade_database(engine)


def _adopt_legacy_workflow_json_schema_revision(engine: Engine) -> None:
    """Bridge databases that applied JSON Schema v4 before Generator evidence was inserted into the chain."""
    config = alembic_config()
    with engine.begin() as connection:
        connection.execute(
            text("update alembic_version set version_num = :revision"),
            {"revision": PRE_GENERATOR_REVISION},
        )
        config.attributes["connection"] = connection
        command.upgrade(config, GENERATOR_REVISION)
        command.stamp(config, CURRENT_WORKFLOW_JSON_SCHEMA_REVISION)
