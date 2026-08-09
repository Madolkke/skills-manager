from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from os import environ

from fastapi import FastAPI
from sqlalchemy import Engine

from skillhub.bootstrap.exceptions import register_exception_handlers
from skillhub.bootstrap.logging_config import configure_logging
from skillhub.bootstrap.middleware import register_middleware
from skillhub.models.schema.database import create_postgres_engine, create_session_factory, resolve_database_url
from skillhub.models.schema.migrations import verify_database_revision
from skillhub.models.store import SkillHubStore
from skillhub.services.workflow_agent_runtime import WorkflowAgentRuntime
from skillhub.services.workflow_agent_settings import WorkflowAgentSettings
from skillhub.views import register_views

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _workflow_agent_lifespan(app: FastAPI):
    await app.state.workflow_agent_runtime.startup()
    try:
        yield
    finally:
        await app.state.workflow_agent_runtime.shutdown()


def create_app(engine: Engine | None = None) -> FastAPI:
    configure_logging(environ)
    logger.info("starting skillhub api")
    app = FastAPI(title="SkillHub API", version="0.1.0", lifespan=_workflow_agent_lifespan)
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
    database_url = app.state.engine.url.render_as_string(hide_password=False)
    app.state.workflow_agent_runtime = WorkflowAgentRuntime(
        lambda: SkillHubStore(app.state.engine),
        WorkflowAgentSettings.from_environment(environ, database_url=database_url),
    )
    register_exception_handlers(app)
    register_views(app)
    logger.info("skillhub api ready")
    return app
