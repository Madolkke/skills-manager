from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from .expression import validate_expression
from .expression.checker_ast import utf16_length


@dataclass(frozen=True)
class TemplateSegment:
    kind: Literal["expression", "unexpected_close", "unclosed"]
    start: int
    end: int


def _expression_end(source: str, start: int) -> int | None:
    """Locate a delimiter outside quoted strings and balanced Python brackets."""
    cursor = start
    quote = ""
    brackets: list[str] = []
    matching = {"(": ")", "[": "]", "{": "}"}
    while cursor < len(source):
        char = source[cursor]
        if quote:
            if char == "\\":
                cursor += 2
            elif source.startswith(quote, cursor):
                cursor += len(quote)
                quote = ""
            else:
                cursor += 1
            continue
        if char in {"'", '"'}:
            quote = char * 3 if source.startswith(char * 3, cursor) else char
            cursor += len(quote)
            continue
        if not brackets and source.startswith("}}", cursor):
            return cursor
        if char in matching:
            brackets.append(matching[char])
        elif brackets and char == brackets[-1]:
            brackets.pop()
        cursor += 1
    return None


def _scan_template(source: str) -> Iterator[TemplateSegment]:
    """Separate complete expressions from unmatched template delimiters."""
    cursor = 0
    while cursor < len(source):
        if source.startswith("}}", cursor):
            yield TemplateSegment("unexpected_close", cursor, cursor + 2)
            cursor += 2
        elif source.startswith("{{", cursor):
            end = _expression_end(source, cursor + 2)
            if end is None:
                yield TemplateSegment("unclosed", cursor, len(source))
                return
            yield TemplateSegment("expression", cursor + 2, end)
            cursor = end + 2
        else:
            cursor += 1


def iter_template_expressions(source: str) -> Iterator[tuple[str, int, int]]:
    """Yield complete template expressions with their original source offsets."""
    for segment in _scan_template(source):
        if segment.kind == "expression":
            yield source[segment.start:segment.end], segment.start, segment.end


def validate_template(source: str, environment: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate delimiters and each embedded expression in a template."""
    diagnostics: list[dict[str, Any]] = []
    for segment in _scan_template(source):
        start, end = segment.start, segment.end
        if segment.kind != "expression":
            code, message = (
                ("TEMPLATE_UNCLOSED", "模板缺少结束标记“}}”。") if segment.kind == "unclosed"
                else ("TEMPLATE_UNEXPECTED_CLOSE", "模板出现未匹配的结束标记。")
            )
            diagnostics.append({
                "severity": "error", "code": code, "message": message,
                "start": utf16_length(source[:start]), "end": utf16_length(source[:end]),
            })
            continue
        expression = source[start:end]
        if not expression.strip():
            diagnostics.append({
                "severity": "error", "code": "TEMPLATE_EMPTY_EXPRESSION", "message": "模板表达式不能为空。",
                "start": utf16_length(source[:start]), "end": utf16_length(source[:end]),
            })
            continue
        result = validate_expression(expression.strip(), environment)
        leading = len(expression) - len(expression.lstrip())
        expression_start = utf16_length(source[:start + leading])
        diagnostics.extend(
            {
                **diagnostic,
                "start": expression_start + diagnostic["start"],
                "end": expression_start + diagnostic["end"],
            }
            for diagnostic in result["diagnostics"]
        )
    return diagnostics
