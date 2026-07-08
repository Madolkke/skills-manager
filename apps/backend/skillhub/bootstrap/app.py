from __future__ import annotations

import logging
from os import environ

from fastapi import FastAPI
from sqlalchemy import Engine

from skillhub.views.dependencies import create_postgres_engine, resolve_database_url
from skillhub.bootstrap.exceptions import register_exception_handlers
from skillhub.bootstrap.logging_config import configure_logging
from skillhub.bootstrap.middleware import register_middleware
from skillhub.models.schema.sync import ensure_current_schema
from skillhub.models.schema.tables import metadata
from skillhub.views import register_views


logger = logging.getLogger(__name__)


def create_app(engine: Engine | None = None) -> FastAPI:
    configure_logging(environ)
    logger.info("starting skillhub api")
    app = FastAPI(title="SkillHub API", version="0.1.0")
    register_middleware(app, environ)
    if engine is None:
        logger.info("creating database engine")
        app.state.engine = create_postgres_engine(resolve_database_url(environ))
    else:
        logger.info("using injected database engine")
        app.state.engine = engine
    logger.info("syncing database schema")
    metadata.create_all(app.state.engine)
    ensure_current_schema(app.state.engine)
    logger.info("database schema ready")
    register_exception_handlers(app)
    register_views(app)
    logger.info("skillhub api ready")
    return app
