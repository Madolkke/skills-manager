"""将领域结果转换为不包含连接凭据的 MCP 工具结果。"""

import json
import logging
from typing import Any

from fastapi.encoders import jsonable_encoder
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError

from skillhub.models.errors import (
    ConflictError,
    FieldInvariantError,
    InvariantError,
    NotFoundError,
    PermissionDeniedError,
)
from skillhub.services.mcp_identity import McpAuthenticationRequired

logger = logging.getLogger(__name__)


def success_result(payload: dict[str, Any]) -> CallToolResult:
    """保留结构化业务结果，并提供简短的中文操作摘要。"""
    encoded = jsonable_encoder(payload)
    summary = str(payload.get("summary") or "操作完成，详细结果见结构化数据。")
    return CallToolResult(
        content=[TextContent(type="text", text=summary), TextContent(type="text", text=json.dumps(encoded, ensure_ascii=False))],
        structuredContent=encoded,
    )


def error_result(error: Exception, tool_name: str) -> CallToolResult:
    """仅暴露已知领域错误，内部异常不输出参数、连接信息或堆栈。"""
    details: dict[str, Any] = {}
    if isinstance(error, McpAuthenticationRequired):
        code, message = "AUTH_REQUIRED", str(error)
    elif isinstance(error, PermissionDeniedError):
        code, message = "PERMISSION_DENIED", str(error)
    elif isinstance(error, NotFoundError):
        code, message = "NOT_FOUND", str(error)
    elif isinstance(error, ConflictError):
        code, message = "CONFLICT", str(error)
    elif isinstance(error, ValidationError):
        code, message = "INVALID_ARGUMENT", "工具参数不符合要求，请按工具 Schema 修改。"
        details["fields"] = [{"path": list(item["loc"]), "code": item["type"]} for item in error.errors(include_input=False)]
    elif isinstance(error, InvariantError):
        code, message = "VALIDATION_FAILED", str(error)
        if isinstance(error, FieldInvariantError):
            details["fields"] = [item.to_payload() for item in error.field_errors]
        if hasattr(error, "validation"):
            details["validation"] = jsonable_encoder(error.validation)
    else:
        code, message = "INTERNAL_ERROR", "工具调用失败，未返回成功；请读取当前状态后再决定是否重试。"
        logger.error("MCP tool failed: tool=%s error_type=%s", tool_name, type(error).__name__)
    payload = {"error": {"code": code, "message": message, **details}}
    return CallToolResult(
        content=[TextContent(type="text", text=f"{code}: {message}"), TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload, isError=True,
    )
