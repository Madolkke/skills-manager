from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from skillhub.models.schema import metadata

BACKEND_ROOT = Path(__file__).resolve().parents[3]


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
    if current_revision(engine) is None:
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
            stamp_database(engine, "0001_orm_baseline")
    upgrade_database(engine)
