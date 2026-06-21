from __future__ import annotations

import os
from urllib.parse import urlsplit

import psycopg
from psycopg import sql
from psycopg.errors import OperationalError
import pytest

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:5432/skillhub_test"


def _normalize_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _database_name(database_url: str) -> str:
    parsed = urlsplit(_normalize_database_url(database_url))
    return parsed.path.lstrip("/")


def _ensure_database(database_url: str) -> None:
    parsed = urlsplit(_normalize_database_url(database_url))
    admin_url = parsed._replace(path="/postgres").geturl()
    database_name = _database_name(database_url)
    with psycopg.connect(admin_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("select 1 from pg_database where datname = %s", (database_name,))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("create database {}").format(sql.Identifier(database_name)))


def ensure_postgres_test_database() -> str:
    test_database_url = os.environ.get("SKILLHUB_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    try:
        _ensure_database(test_database_url)
    except OperationalError as error:
        pytest.skip(f"PostgreSQL test database is unavailable: {error}", allow_module_level=True)
    os.environ.setdefault("SKILLHUB_TEST_DATABASE_URL", test_database_url)
    os.environ["SKILLHUB_DATABASE_URL"] = test_database_url
    return test_database_url
