from __future__ import annotations

import json
from typing import Any

from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import FunctionTool, ToolChunk, Toolkit


def build_workflow_agent_toolkit(context: dict[str, Any], tool_names: tuple[str, ...]) -> Toolkit:
    tools = {
        "read_workflow_context": FunctionTool(
            lambda: _text_response(context),
            name="read_workflow_context",
            description="读取当前 Workflow、当前选择、相关采集定义和最近可见对话。",
            is_read_only=True,
        ),
        "read_workflow_validation": FunctionTool(
            lambda: _text_response(context.get("validationIssues", [])),
            name="read_workflow_validation",
            description="读取当前 Workflow 的确定性校验问题。",
            is_read_only=True,
        ),
        "read_existing_debug_cases": FunctionTool(
            lambda: _text_response(context.get("existingDebugCases", [])),
            name="read_existing_debug_cases",
            description="读取当前 Step 已有的单步调试例。",
            is_read_only=True,
        ),
    }
    return Toolkit(tools=[tools[name] for name in tool_names])


def _text_response(value: object) -> ToolChunk:
    return ToolChunk(
        content=[TextBlock(text=json.dumps(value, ensure_ascii=False, separators=(",", ":")))],
        state=ToolResultState.SUCCESS,
        is_last=True,
    )


__all__ = ["build_workflow_agent_toolkit"]
