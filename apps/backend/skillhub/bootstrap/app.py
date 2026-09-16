from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import environ

from fastapi import FastAPI
from sqlalchemy import Engine

from skillhub.bootstrap.exceptions import register_exception_handlers
from skillhub.bootstrap.logging_config import configure_logging
from skillhub.bootstrap.middleware import register_middleware
from skillhub.models.schema.database import create_postgres_engine, create_session_factory, resolve_database_url
from skillhub.models.schema.migrations import verify_database_revision
from skillhub.views import register_views
from skillhub.views.mcp import register_mcp

logger = logging.getLogger(__name__)


@asynccontextmanager
async def application_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """父应用负责 MCP session manager 生命周期；子应用挂载不自动运行 lifespan。"""
    async with app.state.mcp_server.session_manager.run():
        yield


def create_app(engine: Engine | None = None) -> FastAPI:
    configure_logging(environ)
    logger.info("starting skillhub api")
    app = FastAPI(title="SkillHub API", version="0.1.0", lifespan=application_lifespan)
    register_middleware(app, environ)
    if engine is None:
        logger.info("creating database engine")
        app.state.engine = create_postgres_engine(resolve_database_url(environ))
    else:
        logger.info("using injected database engine")
        app.state.engine = engine
    app.state.session_factory = create_session_factory(app.state.engine)
    logger.info("checking database schema revision")
    verify_database_revision(app.state.engine)
    logger.info("database schema revision ready")
    register_exception_handlers(app)
    register_views(app)
    register_mcp(app)
    logger.info("skillhub api ready")
    return app
