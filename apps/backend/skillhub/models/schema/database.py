from __future__ import annotations

from os import environ
from typing import Mapping

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

POSTGRESQL_SCHEMES = ("postgresql://", "postgresql+psycopg://")


def resolve_database_url(environment: Mapping[str, str] = environ) -> str:
    database_url = environment.get("SKILLHUB_DATABASE_URL")
    if not database_url:
        raise ValueError("SKILLHUB_DATABASE_URL is required and must point to a PostgreSQL database.")
    validate_postgres_url(database_url)
    return database_url


def create_postgres_engine(database_url: str, environment: Mapping[str, str] = environ) -> Engine:
    validate_postgres_url(database_url)
    connect_timeout = _positive_int(environment, "SKILLHUB_DATABASE_CONNECT_TIMEOUT_SECONDS", 10)
    statement_timeout = _positive_int(environment, "SKILLHUB_DATABASE_STATEMENT_TIMEOUT_MS", 30_000)
    lock_timeout = _positive_int(environment, "SKILLHUB_DATABASE_LOCK_TIMEOUT_MS", 5_000)
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": connect_timeout,
            "options": f"-c statement_timeout={statement_timeout} -c lock_timeout={lock_timeout}",
        },
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def validate_postgres_url(database_url: str) -> None:
    if not database_url.startswith(POSTGRESQL_SCHEMES):
        raise ValueError("SKILLHUB_DATABASE_URL must use postgresql:// or postgresql+psycopg://.")


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environment.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value
