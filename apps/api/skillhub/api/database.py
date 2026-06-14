from __future__ import annotations

from os import environ
from typing import Mapping

from fastapi import Request
from sqlalchemy import Engine, create_engine

from skillhub.infrastructure.db.repositories import SqlSkillRepository


POSTGRESQL_SCHEMES = ("postgresql://", "postgresql+psycopg://")


def resolve_database_url(environment: Mapping[str, str] = environ) -> str:
    database_url = environment.get("SKILLHUB_DATABASE_URL")
    if not database_url:
        raise ValueError("SKILLHUB_DATABASE_URL is required and must point to a PostgreSQL database.")
    validate_postgres_url(database_url)
    return database_url


def create_postgres_engine(database_url: str) -> Engine:
    validate_postgres_url(database_url)
    return create_engine(database_url, pool_pre_ping=True)


def validate_postgres_url(database_url: str) -> None:
    if not database_url.startswith(POSTGRESQL_SCHEMES):
        raise ValueError("SKILLHUB_DATABASE_URL must use postgresql:// or postgresql+psycopg://.")


def repository_dependency(request: Request) -> SqlSkillRepository:
    return SqlSkillRepository(request.app.state.engine)
