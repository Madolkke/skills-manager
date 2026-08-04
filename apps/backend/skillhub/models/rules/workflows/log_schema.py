from __future__ import annotations

from typing import Any

from .schema import DOCUMENT_SCHEMA_VERSION

_LOG_COLUMNS = (
    {
        "name": "event_time",
        "duckdb_type": "TIMESTAMP",
        "nullable": True,
        "title": "时间",
        "description": "日志事件时间（无时区）",
    },
    {
        "name": "device",
        "duckdb_type": "VARCHAR",
        "nullable": True,
        "title": "设备",
        "description": "日志来源设备",
    },
    {
        "name": "module",
        "duckdb_type": "VARCHAR",
        "nullable": True,
        "title": "模块",
        "description": "产生日志的模块",
    },
    {
        "name": "severity",
        "duckdb_type": "VARCHAR",
        "nullable": True,
        "title": "严重等级",
        "description": "日志严重等级",
    },
    {
        "name": "brief",
        "duckdb_type": "VARCHAR",
        "nullable": True,
        "title": "简述",
        "description": "日志摘要",
    },
    {
        "name": "body",
        "duckdb_type": "VARCHAR",
        "nullable": True,
        "title": "日志体",
        "description": "原始日志正文",
    },
)

LOG_COLUMN_NAMES = tuple(item["name"] for item in _LOG_COLUMNS)


def workflow_log_schema_catalog() -> dict[str, Any]:
    """Return the fixed v5 logs/params SQL contract."""
    return {
        "document_schema_version": DOCUMENT_SCHEMA_VERSION,
        "dialect": "duckdb",
        "logs_table": "logs",
        "params_table": "params",
        "columns": [dict(item) for item in _LOG_COLUMNS],
    }


__all__ = ["LOG_COLUMN_NAMES", "workflow_log_schema_catalog"]
