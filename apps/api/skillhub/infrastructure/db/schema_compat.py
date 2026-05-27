from __future__ import annotations

from sqlalchemy import Engine, inspect, text


def ensure_sqlite_schema_compatibility(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "skills" in tables:
            add_column_if_missing(inspector, connection, "skills", "current_version_id", "TEXT")
        if "eval_sets" in tables:
            add_column_if_missing(inspector, connection, "eval_sets", "current_version_id", "TEXT")
        if "eval_cases" in tables:
            add_column_if_missing(inspector, connection, "eval_cases", "current_version_id", "TEXT")
        if "skill_versions" in tables:
            add_column_if_missing(inspector, connection, "skill_versions", "display_name", "TEXT")
        if "eval_set_versions" in tables:
            add_column_if_missing(inspector, connection, "eval_set_versions", "display_name", "TEXT")
        backfill_current_pointers(connection, tables)


def add_column_if_missing(inspector, connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return
    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def backfill_current_pointers(connection, tables: set[str]) -> None:
    if {"skills", "skill_versions"}.issubset(tables):
        connection.execute(
            text(
                """
                UPDATE skills
                SET current_version_id = (
                  SELECT id
                  FROM skill_versions
                  WHERE skill_versions.skill_id = skills.id
                  ORDER BY version_number DESC
                  LIMIT 1
                )
                WHERE current_version_id IS NULL
                """
            )
        )
    if {"eval_sets", "eval_set_versions"}.issubset(tables):
        connection.execute(
            text(
                """
                UPDATE eval_sets
                SET current_version_id = (
                  SELECT id
                  FROM eval_set_versions
                  WHERE eval_set_versions.eval_set_id = eval_sets.id
                  ORDER BY version_number DESC
                  LIMIT 1
                )
                WHERE current_version_id IS NULL
                """
            )
        )
    if {"eval_cases", "eval_case_versions"}.issubset(tables):
        connection.execute(
            text(
                """
                UPDATE eval_cases
                SET current_version_id = (
                  SELECT id
                  FROM eval_case_versions
                  WHERE eval_case_versions.case_id = eval_cases.id
                  ORDER BY version_number DESC
                  LIMIT 1
                )
                WHERE current_version_id IS NULL
                """
            )
        )
