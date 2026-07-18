from __future__ import annotations

import logging
from os import environ
from time import perf_counter
from typing import Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

DEFAULT_CORS_ALLOW_ORIGIN_REGEX = (
    r"https?://(?:"
    r"localhost|"
    r"(?:\d{1,3}\.){3}\d{1,3}|"
    r"\[[0-9A-Fa-f:.]+\]|"
    r"[A-Za-z0-9.-]+"
    r")(?::\d+)?"
)
REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger(__name__)


def register_middleware(app: FastAPI, environment: Mapping[str, str] = environ) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allow_origins(environment),
        allow_origin_regex=cors_allow_origin_regex(environment),
        allow_credentials=True,
        allow_private_network=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = _request_id(request)
        request.state.request_id = request_id
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = _duration_ms(started_at)
            logger.exception(
                "request failed request_id=%s method=%s path=%s status=%s duration_ms=%s client=%s",
                request_id,
                request.method,
                request.url.path,
                500,
                duration_ms,
                _client_host(request),
            )
            response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
        duration_ms = _duration_ms(started_at)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request completed request_id=%s method=%s path=%s status=%s duration_ms=%s client=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            _client_host(request),
        )
        return response


def cors_allow_origins(environment: Mapping[str, str]) -> list[str]:
    value = environment.get("SKILLHUB_CORS_ALLOW_ORIGINS", "")
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


def cors_allow_origin_regex(environment: Mapping[str, str]) -> str:
    return environment.get("SKILLHUB_CORS_ALLOW_ORIGIN_REGEX", DEFAULT_CORS_ALLOW_ORIGIN_REGEX)


def _request_id(request: Request) -> str:
    value = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if value:
        return value[:128]
    return str(uuid4())


def _duration_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _client_host(request: Request) -> str:
    return request.client.host if request.client else ""
