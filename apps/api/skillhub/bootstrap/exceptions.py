from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from skillhub.views.responses import error_payload, request_validation_field_errors
from skillhub.models.errors import InvariantError, NotFoundError, PermissionDeniedError


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
