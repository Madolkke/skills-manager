from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .expression import validate_expression


def iter_template_expressions(source: str) -> Iterator[tuple[str, int, int]]:
    """Yield template expression text and its source offsets."""
    cursor = 0
    while cursor < len(source):
        opening = source.find("{{", cursor)
        closing = source.find("}}", cursor)
        if closing >= 0 and (opening < 0 or closing < opening):
            yield "", closing, closing + 2
            cursor = closing + 2
            continue
        if opening < 0:
            return
        closing = source.find("}}", opening + 2)
        if closing < 0:
            yield source[opening + 2 :], opening + 2, len(source)
            return
        yield source[opening + 2 : closing], opening + 2, closing
        cursor = closing + 2


def validate_template(source: str, environment: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate delimiters and each embedded expression in a template."""
    diagnostics: list[dict[str, Any]] = []
    for expression, start, end in iter_template_expressions(source):
        if start == end:
            if source[max(start - 2, 0) : start] == "{{":
                diagnostics.append({"severity": "error", "code": "TEMPLATE_UNCLOSED", "message": "模板缺少结束标记“}}”。", "start": max(start - 2, 0), "end": len(source)})
                if not expression.strip():
                    diagnostics.append({"severity": "error", "code": "TEMPLATE_EMPTY_EXPRESSION", "message": "模板表达式不能为空。", "start": start, "end": end})
                continue
            diagnostics.append({"severity": "error", "code": "TEMPLATE_UNEXPECTED_CLOSE", "message": "模板出现未匹配的结束标记。", "start": start, "end": end + 2})
            continue
        if source[start - 2 : start] != "{{":
            continue
        if end == len(source) and not source.endswith("}}"):
            diagnostics.append({"severity": "error", "code": "TEMPLATE_UNCLOSED", "message": "模板缺少结束标记“}}”。", "start": max(start - 2, 0), "end": len(source)})
        if not expression.strip():
            diagnostics.append({"severity": "error", "code": "TEMPLATE_EMPTY_EXPRESSION", "message": "模板表达式不能为空。", "start": start, "end": end})
            continue
        result = validate_expression(expression.strip(), environment)
        leading = len(expression) - len(expression.lstrip())
        diagnostics.extend(
            {
                **diagnostic,
                "start": start + leading + diagnostic["start"],
                "end": start + leading + diagnostic["end"],
            }
            for diagnostic in result["diagnostics"]
        )
    return diagnostics
