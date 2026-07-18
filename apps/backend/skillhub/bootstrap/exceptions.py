from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from skillhub.models.errors import ConflictError, InvariantError, NotFoundError, PermissionDeniedError
from skillhub.views.responses import error_payload, request_validation_field_errors

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    def not_found_handler(request, exc: NotFoundError):
        _log_warning(request, exc, 404)
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvariantError)
    def invariant_handler(request, exc: InvariantError):
        _log_warning(request, exc, 400)
        return JSONResponse(status_code=400, content=error_payload(exc))

    @app.exception_handler(ConflictError)
    def conflict_handler(request, exc: ConflictError):
        _log_warning(request, exc, 409)
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    def validation_error_handler(request, exc: RequestValidationError):
        logger.warning(
            "request validation error request_id=%s method=%s path=%s status=%s error_count=%s",
            _request_id(request),
            request.method,
            request.url.path,
            422,
            len(exc.errors()),
        )
        return JSONResponse(
            status_code=422,
            content={"detail": "请求字段不完整或格式不正确。", "field_errors": request_validation_field_errors(exc.errors())},
        )

    @app.exception_handler(PermissionDeniedError)
    def permission_denied_handler(request, exc: PermissionDeniedError):
        _log_warning(request, exc, 403)
        return JSONResponse(status_code=403, content={"detail": str(exc)})


def _log_warning(request, exc: Exception, status_code: int) -> None:
    logger.warning(
        "request rejected request_id=%s method=%s path=%s status=%s error_type=%s message=%s",
        _request_id(request),
        request.method,
        request.url.path,
        status_code,
        exc.__class__.__name__,
        str(exc),
    )


def _request_id(request) -> str:
    return str(getattr(request.state, "request_id", ""))
