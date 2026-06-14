from __future__ import annotations

from os import environ
from typing import Mapping

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


DEFAULT_CORS_ALLOW_ORIGIN_REGEX = (
    r"https?://(?:"
    r"localhost|"
    r"(?:\d{1,3}\.){3}\d{1,3}|"
    r"\[[0-9A-Fa-f:.]+\]|"
    r"[A-Za-z0-9.-]+"
    r")(?::\d+)?"
)


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


def cors_allow_origins(environment: Mapping[str, str]) -> list[str]:
    value = environment.get("SKILLHUB_CORS_ALLOW_ORIGINS", "")
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]


def cors_allow_origin_regex(environment: Mapping[str, str]) -> str:
    return environment.get("SKILLHUB_CORS_ALLOW_ORIGIN_REGEX", DEFAULT_CORS_ALLOW_ORIGIN_REGEX)
