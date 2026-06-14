from __future__ import annotations

from skillhub.api.database import create_postgres_engine, resolve_database_url
from skillhub.bootstrap.app import create_app


__all__ = [
    "app",
    "create_app",
    "create_postgres_engine",
    "resolve_database_url",
]

app = create_app()
