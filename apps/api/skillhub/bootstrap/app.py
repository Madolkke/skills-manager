from __future__ import annotations

from os import environ

from fastapi import FastAPI
from sqlalchemy import Engine

from skillhub.api.database import create_postgres_engine, resolve_database_url
from skillhub.api.routes import register_routes
from skillhub.bootstrap.exceptions import register_exception_handlers
from skillhub.bootstrap.middleware import register_middleware
from skillhub.infrastructure.db.tables import metadata


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="SkillHub API", version="0.1.0")
    register_middleware(app, environ)
    app.state.engine = engine or create_postgres_engine(resolve_database_url(environ))
    metadata.create_all(app.state.engine)
    register_exception_handlers(app)
    register_routes(app)
    return app
