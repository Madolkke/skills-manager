from __future__ import annotations

import logging
from os import environ
from typing import Mapping


DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
SUPPORTED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_logging(environment: Mapping[str, str] = environ) -> int:
    """Configure SkillHub application loggers from environment variables."""
    level_name = _log_level_name(environment.get("SKILLHUB_LOG_LEVEL"))
    level = logging.getLevelName(level_name)
    if not logging.getLogger().handlers:
        logging.basicConfig(level=level, format=LOG_FORMAT)
    for logger_name in ("skillhub", "skillhub_worker"):
        logging.getLogger(logger_name).setLevel(level)
    if level_name != _raw_log_level_name(environment.get("SKILLHUB_LOG_LEVEL")):
        logging.getLogger(__name__).warning(
            "invalid log level configured env_var=SKILLHUB_LOG_LEVEL value=%r fallback=%s",
            environment.get("SKILLHUB_LOG_LEVEL"),
            DEFAULT_LOG_LEVEL,
        )
    return int(level)


def _log_level_name(value: str | None) -> str:
    level_name = _raw_log_level_name(value)
    if level_name in SUPPORTED_LOG_LEVELS:
        return level_name
    return DEFAULT_LOG_LEVEL


def _raw_log_level_name(value: str | None) -> str:
    return (value or DEFAULT_LOG_LEVEL).strip().upper() or DEFAULT_LOG_LEVEL
