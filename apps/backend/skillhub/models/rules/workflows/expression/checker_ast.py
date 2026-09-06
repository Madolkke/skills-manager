from __future__ import annotations

import ast

from .types import TypeSpec


def utf16_length(source: str) -> int:
    """Count the code units used by browser editor positions."""
    return len(source.encode("utf-16-le", errors="surrogatepass")) // 2


def source_offset(source: str, line: int, column: int, *, utf8_column: bool = True) -> int:
    """Translate AST UTF8 columns or SyntaxError character columns to UTF16."""
    lines = source.splitlines(keepends=True)
    index = max(line - 1, 0)
    previous = "".join(lines[:index])
    current = lines[index] if index < len(lines) else ""
    prefix = current.encode("utf-8")[:column].decode("utf-8", errors="ignore") if utf8_column else current[:column]
    return utf16_length(previous) + utf16_length(prefix)


def is_config_expression(node: ast.AST) -> bool:
    """Find the root name beneath an attribute or subscript chain."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return isinstance(node, ast.Name) and node.id == "config"


def integer_index_type(value: TypeSpec) -> bool:
    """Allow integer and unknown sample indices while rejecting other types."""
    if value.kind in {"any", "integer"}:
        return True
    return value.kind == "union" and all(option.kind == "integer" for option in value.options)


def integer_literal(node: ast.AST) -> int | None:
    """Read a possibly signed integer AST literal without accepting booleans."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        value = node.operand.value
        if isinstance(value, int) and not isinstance(value, bool):
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
    return None
