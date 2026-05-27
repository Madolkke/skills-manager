from __future__ import annotations

from os import environ
from pathlib import Path
from typing import Mapping

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.pool import StaticPool

from skillhub.infrastructure.db.repositories import SqlSkillRepository


def create_local_sqlite_engine() -> Engine:
    return create_sqlite_engine("sqlite:///:memory:")


def resolve_database_url(environment: Mapping[str, str] = environ) -> str:
    if environment.get("SKILLHUB_DATABASE_URL"):
        return environment["SKILLHUB_DATABASE_URL"]
    data_dir = Path(environment.get("SKILLHUB_DATA_DIR", default_data_dir()))
    return sqlite_file_url(data_dir / "skillhub.sqlite3")


def default_data_dir() -> Path:
    return Path(__file__).resolve().parents[4] / ".data"


def sqlite_file_url(path: str | Path) -> str:
    database_path = Path(path).expanduser().resolve()
    return f"sqlite:///{database_path.as_posix()}"


def create_sqlite_engine(database_url: str) -> Engine:
    if database_url == "sqlite:///:memory:":
        engine = create_engine(database_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        sqlite_path = sqlite_path_from_url(database_url)
        if sqlite_path is not None:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(database_url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    return engine


def sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return None
    raw_path = database_url.removeprefix("sqlite:///")
    if not raw_path:
        return None
    return Path(raw_path)


def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    dbapi_connection.execute("pragma foreign_keys=on")


def repository_dependency(request: Request) -> SqlSkillRepository:
    return SqlSkillRepository(request.app.state.engine)
