from __future__ import annotations

from os import environ

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from skillhub.api.database import create_local_sqlite_engine, create_sqlite_engine, resolve_database_url
from skillhub.api.responses import error_payload, request_validation_field_errors
from skillhub.api.routes_commands import register_command_routes
from skillhub.api.routes_core import register_core_routes
from skillhub.api.routes_history import register_history_routes
from skillhub.domain.errors import InvariantError, NotFoundError, PermissionDeniedError
from skillhub.infrastructure.db.schema_compat import ensure_sqlite_schema_compatibility
from skillhub.infrastructure.db.tables import metadata


__all__ = [
    "app",
    "create_app",
    "create_local_sqlite_engine",
    "create_sqlite_engine",
    "resolve_database_url",
]


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="SkillHub API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(127\.0\.0\.1|localhost):\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.engine = engine or create_sqlite_engine(resolve_database_url(environ))
    metadata.create_all(app.state.engine)
    ensure_sqlite_schema_compatibility(app.state.engine)
    register_exception_handlers(app)
    register_core_routes(app)
    register_history_routes(app)
    register_command_routes(app)
    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    def not_found_handler(_request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvariantError)
    def invariant_handler(_request, exc: InvariantError):
        return JSONResponse(status_code=400, content=error_payload(exc))

    @app.exception_handler(RequestValidationError)
    def validation_error_handler(_request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": "请求字段不完整或格式不正确。", "field_errors": request_validation_field_errors(exc.errors())},
        )

    @app.exception_handler(PermissionDeniedError)
    def permission_denied_handler(_request, exc: PermissionDeniedError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})


app = create_app()
