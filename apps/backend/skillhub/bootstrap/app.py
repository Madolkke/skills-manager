from __future__ import annotations

from os import environ

from fastapi import FastAPI
from sqlalchemy import Engine

from skillhub.views.dependencies import create_postgres_engine, resolve_database_url
from skillhub.bootstrap.exceptions import register_exception_handlers
from skillhub.bootstrap.middleware import register_middleware
from skillhub.models.schema.sync import ensure_current_schema
from skillhub.models.schema.tables import metadata
from skillhub.views import register_views


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="SkillHub API", version="0.1.0")
    register_middleware(app, environ)
    app.state.engine = engine or create_postgres_engine(resolve_database_url(environ))
    metadata.create_all(app.state.engine)
    ensure_current_schema(app.state.engine)
    register_exception_handlers(app)
    register_views(app)
    return app
