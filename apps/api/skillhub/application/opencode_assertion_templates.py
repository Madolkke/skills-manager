from __future__ import annotations

import json
from typing import Any

from skillhub.application.assertion_base import AssertionContext, AssertionParam, AssertionResult, AssertionTemplate
from skillhub.domain.errors import InvariantError


OPENCODE_CATEGORY = "Opencode 过程"


class ToolCalledTemplate(AssertionTemplate):
    id = "tool_called"
    name = "调用过指定工具"
    description = "检查本步骤是否至少调用过指定 Opencode 工具。"
    category = OPENCODE_CATEGORY
    params = (AssertionParam("tool", "工具名", "text", placeholder="例如：read"),)

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        tool = _tool_name(params)
        calls = _matching_tool_calls(context, tool)
        passed = len(calls) > 0
        return AssertionResult(passed, _tool_summary(context.tool_calls), "已调用指定工具。" if passed else "未调用指定工具。", {"tool": tool, "count": len(calls)})


class ToolNotCalledTemplate(ToolCalledTemplate):
    id = "tool_not_called"
    name = "未调用指定工具"
    description = "检查本步骤没有调用指定 Opencode 工具。"

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        tool = _tool_name(params)
        calls = _matching_tool_calls(context, tool)
        passed = len(calls) == 0
        return AssertionResult(passed, _tool_summary(context.tool_calls), "未调用指定工具。" if passed else "调用了不应使用的工具。", {"tool": tool, "count": len(calls)})


class ToolCallCountTemplate(AssertionTemplate):
    id = "tool_call_count"
    name = "工具调用次数满足条件"
    description = "检查指定工具调用次数是否等于、至少或至多某个数量。"
    category = OPENCODE_CATEGORY
    params = (
        AssertionParam("tool", "工具名", "text", placeholder="例如：read"),
        AssertionParam("operator", "比较方式", "text", default="at_least", placeholder="equals / at_least / at_most"),
        AssertionParam("count", "次数", "number", default=1, min=0),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        tool = _tool_name(params)
        operator = str(params.get("operator") or "at_least").strip()
        expected = _non_negative_int(params.get("count"), "count")
        actual = len(_matching_tool_calls(context, tool))
        if operator == "equals":
            passed = actual == expected
            label = "等于"
        elif operator == "at_least":
            passed = actual >= expected
            label = "至少"
        elif operator == "at_most":
            passed = actual <= expected
            label = "至多"
        else:
            raise InvariantError("Tool call count operator must be equals, at_least or at_most.")
        return AssertionResult(passed, _tool_summary(context.tool_calls), f"{tool} 调用 {actual} 次，要求{label} {expected} 次。", {"tool": tool, "operator": operator, "expected": expected, "actual": actual})


class ToolCallInputContainsTemplate(AssertionTemplate):
    id = "tool_call_input_contains"
    name = "工具调用参数包含文本"
    description = "检查指定工具的调用参数中是否包含给定文本。"
    category = OPENCODE_CATEGORY
    params = (
        AssertionParam("tool", "工具名", "text", placeholder="例如：read"),
        AssertionParam("text", "参数包含", "textarea", placeholder="例如：filePath 或 README.md"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        tool = _tool_name(params)
        needle = str(params["text"])
        calls = _matching_tool_calls(context, tool)
        matched = [call for call in calls if needle in _input_text(call)]
        passed = len(matched) > 0
        return AssertionResult(passed, _tool_summary(context.tool_calls), "工具参数包含指定文本。" if passed else "工具参数未包含指定文本。", {"tool": tool, "text": needle, "matching_calls": len(matched), "count": len(calls)})


class ReasoningContainsTemplate(AssertionTemplate):
    id = "reasoning_contains"
    name = "reasoning 包含文本"
    description = "检查 Opencode 返回的 reasoning 内容是否包含指定文本。"
    category = OPENCODE_CATEGORY
    params = (AssertionParam("text", "必须包含", "textarea", placeholder="填写 reasoning 中应出现的文本"),)

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        needle = str(params["text"])
        passed = needle in context.reasoning_text
        return AssertionResult(passed, context.reasoning_text, "reasoning 包含指定文本。" if passed else "reasoning 未包含指定文本。", {"text": needle})


class ReasoningNotContainsTemplate(ReasoningContainsTemplate):
    id = "reasoning_not_contains"
    name = "reasoning 不包含文本"
    description = "检查 Opencode 返回的 reasoning 内容不包含指定文本。"

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        needle = str(params["text"])
        passed = needle not in context.reasoning_text
        return AssertionResult(passed, context.reasoning_text, "reasoning 未包含指定文本。" if passed else "reasoning 包含了不应出现的文本。", {"text": needle})


def opencode_process_templates() -> tuple[AssertionTemplate, ...]:
    return (
        ToolCalledTemplate(),
        ToolNotCalledTemplate(),
        ToolCallCountTemplate(),
        ToolCallInputContainsTemplate(),
        ReasoningContainsTemplate(),
        ReasoningNotContainsTemplate(),
    )


def _tool_name(params: dict[str, Any]) -> str:
    tool = str(params.get("tool") or "").strip()
    if not tool:
        raise InvariantError("Tool name is required.")
    return tool


def _matching_tool_calls(context: AssertionContext, tool: str) -> list[dict[str, Any]]:
    return [call for call in context.tool_calls if str(call.get("tool") or "") == tool]


def _input_text(call: dict[str, Any]) -> str:
    value = call.get("input")
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _tool_summary(calls: list[dict[str, Any]]) -> str:
    if not calls:
        return "未捕获到工具调用。"
    rows = []
    for call in calls:
        tool = str(call.get("tool") or "-")
        status = str(call.get("status") or "-")
        input_text = _input_text(call)
        rows.append(f"{tool} [{status}] {input_text}".strip())
    return "\n".join(rows)


def _non_negative_int(value: Any, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise InvariantError(f"{name} must be a non-negative integer.") from exc
    if parsed < 0:
        raise InvariantError(f"{name} must be a non-negative integer.")
    return parsed
